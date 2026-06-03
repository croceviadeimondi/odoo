"""
Modello `crocevia.registro.vidimazione`: eventi di firma+marca temporale
applicati al registro volontari (art. 2215-bis cc).

Workflow:
  bozza -> pdf_generato -> firmato_verificato

NOTA SCOPE v1.0: la verifica crittografica della firma PAdES via pyHanko
non e' attiva. La transizione da `pdf_generato` a `firmato_verificato`
e' manuale: il responsabile carica il PDF firmato, dichiara la data
della marca temporale e il flag `firma_valida=True`. La verifica
crittografica reale (pyHanko + bundle CA AgID) verra' aggiunta in
v2.0 e renderà i campi `firma_valida` e `firma_dettagli` computed
read-only invece che manuali.

Per ora si fida del responsabile sul fatto che il PDF caricato sia
effettivamente firmato e marcato. La traccia formale resta:
- pdf_unsigned_hash = SHA-256 dello snapshot generato dal modulo
- pdf_signed = file caricato (bytes)
- responsabile_id = chi ha "vidimato"
- chatter = audit log
"""

import base64
import glob
import hashlib
import logging
import os

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..utils.verifica_pades import verifica_pdf_firmato

_logger = logging.getLogger(__name__)

PARAM_STRICT = 'crocevia_registro_volontari.firma_strict'


STATO_SELECTION = [
    ('bozza', 'Bozza'),
    ('pdf_generato', 'PDF generato'),
    ('firmato_verificato', 'Firmato e verificato'),
    ('errore', 'Errore'),
]


class CroceviaRegistroVidimazione(models.Model):
    _name = 'crocevia.registro.vidimazione'
    _description = "Vidimazione del registro volontari"
    _inherit = ['mail.thread']
    _order = 'data_snapshot desc, id desc'

    name = fields.Char(
        string="Nome",
        compute='_compute_name',
        store=True,
    )
    data_snapshot = fields.Datetime(
        string="Data snapshot",
        default=fields.Datetime.now,
        readonly=True,
        copy=False,
    )
    iscrizioni_count = fields.Integer(
        string="N. iscritti nello snapshot",
        readonly=True,
        copy=False,
    )

    pdf_unsigned = fields.Binary(
        string="PDF non firmato",
        copy=False,
        attachment=True,
    )
    pdf_unsigned_filename = fields.Char(
        string="Nome file PDF non firmato",
        readonly=True,
    )
    pdf_unsigned_hash = fields.Char(
        string="Hash SHA-256 PDF non firmato",
        size=64,
        readonly=True,
        copy=False,
    )

    pdf_signed = fields.Binary(
        string="PDF firmato + marcato",
        copy=False,
        attachment=True,
        help="Carica il PDF dopo averlo firmato esternamente con il tuo "
             "software (ArubaSign / GoSign / Dike / Namirial Firma Pro) "
             "e averlo marcato temporalmente (RFC 3161 PAdES-T).",
    )
    pdf_signed_filename = fields.Char(string="Nome file PDF firmato")

    firma_valida = fields.Boolean(
        string="Firma valida",
        default=False,
        tracking=True,
        help="Flag manuale (v1.0): il responsabile dichiara di aver "
             "verificato esternamente che il PDF e' firmato con FEQ "
             "+ marca temporale. In v2.0 sara' computed da pyHanko.",
    )
    firma_dettagli = fields.Text(
        string="Dettagli verifica",
        help="Output testuale della verifica firma. In v1.0: "
             "annotazione manuale del responsabile (es. 'ArubaSign "
             "con FEQ di Lele Damato, marca temporale Aruba TSA').",
    )
    firmatario_nome = fields.Char(string="Nome firmatario")
    firmatario_cf = fields.Char(string="CF firmatario")
    marca_temporale_data = fields.Datetime(
        string="Data marca temporale",
        tracking=True,
    )
    tsa_provider = fields.Char(string="TSA provider")

    stato = fields.Selection(
        selection=STATO_SELECTION,
        string="Stato",
        default='bozza',
        readonly=True,
        copy=False,
        tracking=True,
    )
    responsabile_id = fields.Many2one(
        'res.users',
        string="Responsabile",
        default=lambda self: self.env.user,
        readonly=True,
    )

    # ----------------- computed -----------------

    @api.depends('data_snapshot')
    def _compute_name(self):
        for v in self:
            if v.data_snapshot:
                v.name = "Vidimazione %s" % v.data_snapshot.strftime('%Y-%m-%d')
            else:
                v.name = "Vidimazione (bozza)"

    # ----------------- workflow -----------------

    def action_genera_snapshot(self):
        """Genera il PDF dello stato corrente del registro e ne calcola
        l'hash. Da `bozza` a `pdf_generato`."""
        self.ensure_one()
        if self.stato != 'bozza':
            raise UserError(_(
                "Snapshot gia' generato per questa vidimazione "
                "(stato: %s)."
            ) % dict(STATO_SELECTION).get(self.stato))

        # Richiama il report QWeb e cattura il PDF.
        Report = self.env['ir.actions.report']
        report_name = 'crocevia_registro_volontari.report_registro_volontari'
        # Passiamo l'id della vidimazione cosi' il template puo'
        # leggere data_snapshot dal contesto invece di mettere now()
        # variabile (per determinismo).
        pdf_content, _content_type = Report.with_context(
            data_snapshot=self.data_snapshot,
        )._render_qweb_pdf(report_name, res_ids=[self.id])

        # Post-processing per determinismo: rimuove timestamp e ID
        # variabili dal PDF cosi' lo stesso snapshot da' sempre lo
        # stesso hash. Richiede `qpdf` installato (Dockerfile).
        pdf_deterministico = self._normalizza_pdf(pdf_content)

        h = hashlib.sha256(pdf_deterministico).hexdigest()
        iscrizioni = self.env['crocevia.registro.iscrizione'].search_count([])

        self.write({
            'pdf_unsigned': pdf_deterministico,
            'pdf_unsigned_filename': self.name + '_da_firmare.pdf',
            'pdf_unsigned_hash': h,
            'iscrizioni_count': iscrizioni,
            'stato': 'pdf_generato',
        })
        self.message_post(body=_(
            "Snapshot generato: %d iscritti, hash %s..."
        ) % (iscrizioni, h[:16]))

    @staticmethod
    def _normalizza_pdf(pdf_bytes):
        """Esegue `qpdf --deterministic-id --object-streams=disable` per
        rimuovere ID e timestamp variabili. Restituisce i bytes
        normalizzati. Se qpdf non e' disponibile, ritorna il PDF
        originale (lo stesso snapshot da' hash diversi in due
        generazioni successive -> WARN nel log)."""
        import subprocess
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as inp:
                inp.write(pdf_bytes)
                inp_name = inp.name
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out:
                out_name = out.name
            subprocess.run(
                ['qpdf', '--deterministic-id', '--linearize',
                 inp_name, out_name],
                check=True, capture_output=True,
            )
            with open(out_name, 'rb') as f:
                return f.read()
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            _logger.warning(
                "qpdf non disponibile o errore: %s. Lo snapshot NON "
                "sara' deterministico tra rigenerazioni successive.",
                e,
            )
            return pdf_bytes

    def _carica_trust_roots(self):
        """Carica i certificati CA (PEM/CRT) da data/trust/ del modulo, se
        presenti, per la validazione della catena verso le CA qualificate.
        Lista vuota se nessuno -> verifica solo integrita'+marca temporale."""
        roots = []
        try:
            from asn1crypto import pem, x509
            base = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'data', 'trust')
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
        """v2.0: verifica CRITTOGRAFICA reale via pyHanko (integrita', firma
        PAdES, copertura, marca temporale RFC 3161; catena CA qualificate
        best-effort). Se valida congela i record bozza e chiude; altrimenti
        stato 'errore' con i dettagli."""
        self.ensure_one()
        if self.stato not in ('pdf_generato', 'errore'):
            raise UserError(_(
                "La verifica firma e' ammessa solo dopo la generazione "
                "dello snapshot."))
        if not self.pdf_signed:
            raise UserError(_("Carica prima il PDF firmato esternamente."))

        pdf_bytes = base64.b64decode(self.pdf_signed)
        strict = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_STRICT, 'False') in ('True', 'true', '1')
        esito = verifica_pdf_firmato(
            pdf_bytes, trust_roots=self._carica_trust_roots(), strict=strict)

        # La marca temporale di pyHanko e' tz-aware: Odoo vuole UTC naive.
        mt = esito.get('marca_temporale')
        if mt is not None and mt.tzinfo is not None:
            from datetime import timezone
            mt = mt.astimezone(timezone.utc).replace(tzinfo=None)

        self.write({
            'firma_valida': esito['valida'],
            'firma_dettagli': esito['dettagli'],
            'firmatario_nome': esito['firmatario_nome'] or self.firmatario_nome,
            'firmatario_cf': esito['firmatario_cf'] or self.firmatario_cf,
            'marca_temporale_data': mt or self.marca_temporale_data,
            'tsa_provider': esito['tsa'] or self.tsa_provider,
        })

        if not esito['valida']:
            self.stato = 'errore'
            self.message_post(body=_(
                "<strong>Verifica firma FALLITA.</strong> Vidimazione NON "
                "chiusa.<br/><pre>%s</pre>") % esito['dettagli'])
            raise UserError(_(
                "Firma non valida: la vidimazione non e' stata chiusa.\n\n%s"
            ) % esito['dettagli'])

        # Firma valida: congela i record bozza (hash chain) e chiude.
        Isc = self.env['crocevia.registro.iscrizione']
        n_congelati = Isc._congela_bozza_per_vidimazione()
        self.stato = 'firmato_verificato'
        self.message_post(body=_(
            "Vidimazione chiusa (firma verificata). %d record congelati. "
            "Firmatario: %s, marca temporale: %s.<br/><pre>%s</pre>"
        ) % (
            n_congelati,
            self.firmatario_nome or '?',
            self.marca_temporale_data.strftime('%d/%m/%Y %H:%M:%S')
                if self.marca_temporale_data else '?',
            esito['dettagli'],
        ))

    # ----------------- inalterabilita' post-chiusura -----------------

    _CAMPI_BLOCCATI_DOPO_FIRMA = frozenset({
        'pdf_unsigned', 'pdf_unsigned_hash', 'data_snapshot',
        'iscrizioni_count', 'pdf_signed', 'firma_valida',
        'marca_temporale_data', 'firmatario_nome', 'firmatario_cf',
        'tsa_provider', 'stato',
    })

    def write(self, vals):
        for r in self:
            if r.stato == 'firmato_verificato':
                violazioni = set(vals.keys()) & self._CAMPI_BLOCCATI_DOPO_FIRMA
                if violazioni:
                    raise UserError(_(
                        "Vidimazione gia' chiusa. Campi bloccati: %s."
                    ) % ", ".join(sorted(violazioni)))
        return super().write(vals)

    def unlink(self):
        for r in self:
            if r.stato == 'firmato_verificato':
                raise UserError(_(
                    "Vidimazione %s gia' chiusa: non puo' essere "
                    "cancellata."
                ) % r.name)
        return super().unlink()

    # ----------------- cron reminder annuale -----------------

    @api.model
    def _cron_alert_vidimazione(self):
        """Eseguito mensilmente da `ir_cron_reminder_vidimazione`.
        Verifica l'eta' dell'ultima vidimazione e posta messaggio
        nel chatter dell'ultima vidimazione (niente email finche' SMTP
        non e' configurato)."""
        from datetime import timedelta
        ultima = self.search(
            [('stato', '=', 'firmato_verificato')],
            order='marca_temporale_data desc', limit=1)
        ora = fields.Datetime.now()
        if not ultima:
            n_isc = self.env['crocevia.registro.iscrizione'].search_count([])
            if n_isc > 0:
                _logger.warning(
                    "Registro volontari: %d iscritti senza alcuna "
                    "vidimazione. Vidimare urgentemente "
                    "(art. 2215-bis cc).", n_isc)
            return
        eta = ora - ultima.marca_temporale_data
        if eta > timedelta(days=365):
            _logger.warning(
                "Registro volontari: ultima vidimazione del %s "
                "(>12 mesi fa). Vidimazione scaduta.",
                ultima.marca_temporale_data.strftime('%d/%m/%Y'))
            ultima.message_post(
                body=_(
                    "<strong>Vidimazione scaduta.</strong> Sono passati "
                    "piu' di 12 mesi dalla marca temporale (%s). Prima "
                    "di registrare nuovi volontari occorre rividimare "
                    "il registro (art. 2215-bis cc)."
                ) % ultima.marca_temporale_data.strftime('%d/%m/%Y'),
                subject=_("Vidimazione scaduta"),
            )
        elif eta > timedelta(days=305):
            ultima.message_post(body=_(
                "Ultima vidimazione: %s. Mancano <60 giorni alla "
                "scadenza dei 12 mesi: pianificare la prossima."
            ) % ultima.marca_temporale_data.strftime('%d/%m/%Y'))
