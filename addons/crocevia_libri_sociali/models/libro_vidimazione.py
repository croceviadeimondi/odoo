"""
Vidimazione periodica dei libri sociali (libro soci, libri dei verbali).

Modello a "snapshot periodico firmato": genera un PDF deterministico del libro
a una certa data, il responsabile lo firma + marca esternamente, il modulo
verifica crittograficamente (riusando il verificatore PAdES del registro
volontari) e sigilla la vidimazione (immutabile). I record dei libri restano
modificabili: la vidimazione e' la "foto firmata" del libro a quella data.
"""
import base64
import glob
import hashlib
import logging
import os
import subprocess
import tempfile
from datetime import timedelta, timezone

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.crocevia_registro_volontari.utils.verifica_pades import (
    verifica_pdf_firmato,
)

_logger = logging.getLogger(__name__)

TIPO_LIBRO_SELECTION = [
    ('soci', 'Libro soci'),
    ('verbali_assemblea', 'Libro verbali assemblee'),
    ('verbali_direttivo', 'Libro verbali direttivo'),
]
STATO_SELECTION = [
    ('bozza', 'Bozza'),
    ('pdf_generato', 'PDF generato'),
    ('firmato_verificato', 'Firmato e verificato'),
    ('errore', 'Errore'),
]
REPORT_PER_TIPO = {
    'soci': 'crocevia_libri_sociali.report_libro_soci',
    'verbali_assemblea': 'crocevia_libri_sociali.report_libro_verbali',
    'verbali_direttivo': 'crocevia_libri_sociali.report_libro_verbali',
}
PARAM_STRICT = 'crocevia_libri_sociali.firma_strict'


class CroceviaLibroVidimazione(models.Model):
    _name = 'crocevia.libro.vidimazione'
    _description = "Vidimazione di un libro sociale"
    _inherit = ['mail.thread']
    _order = 'data_snapshot desc, id desc'

    tipo_libro = fields.Selection(
        selection=TIPO_LIBRO_SELECTION, string="Libro",
        required=True, readonly=True, copy=False, tracking=True,
        default=lambda self: self.env.context.get('default_tipo_libro', 'soci'))
    name = fields.Char(string="Nome", compute='_compute_name', store=True)
    data_snapshot = fields.Datetime(
        string="Data snapshot", default=fields.Datetime.now,
        readonly=True, copy=False)
    record_count = fields.Integer(
        string="Voci nello snapshot", readonly=True, copy=False)

    pdf_unsigned = fields.Binary(string="PDF da firmare", copy=False, attachment=True)
    pdf_unsigned_filename = fields.Char(readonly=True)
    pdf_unsigned_hash = fields.Char(string="Hash SHA-256", size=64, readonly=True, copy=False)
    pdf_signed = fields.Binary(string="PDF firmato + marcato", copy=False, attachment=True,
        help="Carica il PDF dopo averlo firmato (FEQ) e marcato (RFC 3161) col tuo software.")
    pdf_signed_filename = fields.Char()

    firma_valida = fields.Boolean(string="Firma valida", readonly=True, tracking=True)
    firma_dettagli = fields.Text(string="Dettagli verifica", readonly=True)
    firmatario_nome = fields.Char(string="Firmatario", readonly=True)
    firmatario_cf = fields.Char(string="CF firmatario", readonly=True)
    marca_temporale_data = fields.Datetime(string="Marca temporale", readonly=True, tracking=True)
    tsa_provider = fields.Char(string="TSA", readonly=True)

    stato = fields.Selection(
        selection=STATO_SELECTION, string="Stato", default='bozza',
        readonly=True, copy=False, tracking=True)
    responsabile_id = fields.Many2one(
        'res.users', string="Responsabile",
        default=lambda self: self.env.user, readonly=True)

    @api.depends('tipo_libro', 'data_snapshot')
    def _compute_name(self):
        etichette = dict(TIPO_LIBRO_SELECTION)
        for v in self:
            libro = etichette.get(v.tipo_libro, v.tipo_libro or '')
            data = v.data_snapshot.strftime('%Y-%m-%d') if v.data_snapshot else '(bozza)'
            v.name = "%s - %s" % (libro, data)

    # ---------------- contenuto dello snapshot ----------------

    def _records_snapshot(self):
        """Recordset del libro fotografato, in ordine deterministico.
        Usato dal template QWeb."""
        self.ensure_one()
        if self.tipo_libro == 'soci':
            return self.env['res.partner'].search(
                [('is_socio', '=', True)], order='numero_socio, id')
        tipo_verbale = ('assemblea_soci' if self.tipo_libro == 'verbali_assemblea'
                        else 'riunione_direttivo')
        dom = [('tipo', '=', tipo_verbale)]
        if self.data_snapshot:
            dom.append(('data', '<=', fields.Date.to_date(self.data_snapshot)))
        return self.env['crocevia.verbale'].search(dom, order='data, id')

    # ---------------- workflow ----------------

    def action_genera_snapshot(self):
        self.ensure_one()
        if self.stato != 'bozza':
            raise UserError(_("Snapshot gia' generato per questa vidimazione."))
        report_name = REPORT_PER_TIPO[self.tipo_libro]
        pdf_content, _ct = self.env['ir.actions.report'].with_context(
            data_snapshot=self.data_snapshot,
        )._render_qweb_pdf(report_name, res_ids=[self.id])
        pdf_det = self._normalizza_pdf(pdf_content)
        h = hashlib.sha256(pdf_det).hexdigest()
        self.write({
            'pdf_unsigned': base64.b64encode(pdf_det),
            'pdf_unsigned_filename': (self.name + '_da_firmare.pdf').replace(' ', '_'),
            'pdf_unsigned_hash': h,
            'record_count': len(self._records_snapshot()),
            'stato': 'pdf_generato',
        })
        self.message_post(body=_(
            "Snapshot generato: %d voci, hash %s...") % (self.record_count, h[:16]))

    @staticmethod
    def _normalizza_pdf(pdf_bytes):
        """qpdf --deterministic-id per uno snapshot riproducibile."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as inp:
                inp.write(pdf_bytes)
                inp_name = inp.name
            out_name = inp_name + '.out.pdf'
            subprocess.run(['qpdf', '--deterministic-id', '--linearize',
                            inp_name, out_name], check=True, capture_output=True)
            with open(out_name, 'rb') as f:
                return f.read()
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            _logger.warning("qpdf non disponibile: %s. Snapshot non deterministico.", e)
            return pdf_bytes

    def _carica_trust_roots(self):
        """Riusa il bundle CA del registro volontari, se presente."""
        roots = []
        try:
            from asn1crypto import pem, x509
            import odoo.addons.crocevia_registro_volontari as regmod
            base = os.path.join(os.path.dirname(regmod.__file__), 'data', 'trust')
            for path in sorted(glob.glob(os.path.join(base, '*.pem'))
                               + glob.glob(os.path.join(base, '*.crt'))):
                with open(path, 'rb') as f:
                    data = f.read()
                if pem.detect(data):
                    for _t, _h, der in pem.unarmor(data, multiple=True):
                        roots.append(x509.Certificate.load(der))
                else:
                    roots.append(x509.Certificate.load(data))
        except Exception as e:  # noqa: BLE001
            _logger.warning("Trust roots non caricati: %s", e)
        return roots

    def action_verifica_firma(self):
        self.ensure_one()
        if self.stato not in ('pdf_generato', 'errore'):
            raise UserError(_("Genera prima lo snapshot."))
        if not self.pdf_signed:
            raise UserError(_("Carica prima il PDF firmato."))
        strict = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_STRICT, 'False') in ('True', 'true', '1')
        esito = verifica_pdf_firmato(
            base64.b64decode(self.pdf_signed),
            trust_roots=self._carica_trust_roots(), strict=strict)
        mt = esito.get('marca_temporale')
        if mt is not None and mt.tzinfo is not None:
            mt = mt.astimezone(timezone.utc).replace(tzinfo=None)
        self.write({
            'firma_valida': esito['valida'],
            'firma_dettagli': esito['dettagli'],
            'firmatario_nome': esito['firmatario_nome'],
            'firmatario_cf': esito['firmatario_cf'],
            'marca_temporale_data': mt,
            'tsa_provider': esito['tsa'],
        })
        if not esito['valida']:
            self.stato = 'errore'
            self.message_post(body=_(
                "<strong>Verifica firma FALLITA.</strong><br/><pre>%s</pre>")
                % esito['dettagli'])
            raise UserError(_("Firma non valida.\n\n%s") % esito['dettagli'])
        self.stato = 'firmato_verificato'
        self.message_post(body=_(
            "Libro vidimato (firma verificata). Firmatario: %s, marca: %s."
            "<br/><pre>%s</pre>") % (
            self.firmatario_nome or '?',
            self.marca_temporale_data.strftime('%d/%m/%Y %H:%M:%S')
                if self.marca_temporale_data else '?',
            esito['dettagli']))

    # ---------------- inalterabilita' post-chiusura ----------------

    _CAMPI_BLOCCATI = frozenset({
        'tipo_libro', 'data_snapshot', 'record_count', 'pdf_unsigned',
        'pdf_unsigned_hash', 'pdf_signed', 'firma_valida',
        'marca_temporale_data', 'firmatario_nome', 'firmatario_cf',
        'tsa_provider', 'stato'})

    def write(self, vals):
        for r in self:
            if r.stato == 'firmato_verificato' and (set(vals) & self._CAMPI_BLOCCATI):
                raise UserError(_(
                    "Vidimazione gia' chiusa: campi non modificabili."))
        return super().write(vals)

    def unlink(self):
        for r in self:
            if r.stato == 'firmato_verificato':
                raise UserError(_(
                    "Vidimazione %s gia' chiusa: non cancellabile.") % r.name)
        return super().unlink()

    # ---------------- cron reminder annuale per libro ----------------

    @api.model
    def _cron_alert_libri(self):
        ora = fields.Datetime.now()
        for tipo, etichetta in TIPO_LIBRO_SELECTION:
            ultima = self.search([
                ('tipo_libro', '=', tipo),
                ('stato', '=', 'firmato_verificato'),
            ], order='marca_temporale_data desc', limit=1)
            if not ultima or not ultima.marca_temporale_data:
                _logger.warning("Libro '%s' mai vidimato.", etichetta)
                continue
            eta = ora - ultima.marca_temporale_data
            if eta > timedelta(days=365):
                ultima.message_post(body=_(
                    "<strong>Vidimazione scaduta</strong> per %s: ultima del %s "
                    "(>12 mesi). Rividimare (art. 2215-bis cc).") % (
                    etichetta,
                    ultima.marca_temporale_data.strftime('%d/%m/%Y')))
