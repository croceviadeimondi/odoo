"""La tessera dentro la miniapp: la propria tessera con mensilita' e
ricevute, e il tesseramento di chi non e' ancora sociə.

Ricevute e richieste di iscrizione stanno in crocevia_tesseramento, e
l'utente tecnico della miniapp non ha i permessi per leggerle: qui si
passa per sudo, sempre filtrando sulla persona che chiede (il telegram_id
verificato dal server) o su una richiesta che il direttivo sta decidendo.
"""
import base64
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# I campi del modulo di iscrizione della miniapp: gli stessi del form del
# sito (crocevia_tesseramento/controllers/main.py).
CAMPI_ISCRIZIONE = (
    'nome', 'cognome', 'data_nascita', 'luogo_nascita', 'codice_fiscale',
    'email', 'telefono', 'indirizzo', 'cap', 'citta', 'provincia', 'messaggio',
)
# Per il libro soci servono le generalita' complete: dalla miniapp si
# chiedono tutte, tranne telefono, provincia e messaggio.
OBBLIGATORI = (
    'nome', 'cognome', 'data_nascita', 'luogo_nascita', 'codice_fiscale',
    'email', 'indirizzo', 'cap', 'citta',
)
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
CF_RE = re.compile(r'^[A-Z0-9]{16}$')
METODI_APPROVAZIONE = ('contanti', 'satispay', 'bonifico')


class CroceviaRichiestaIscrizione(models.Model):
    _inherit = 'crocevia.richiesta.iscrizione'

    telegram_id = fields.Char(
        string="Telegram ID",
        copy=False,
        index=True,
        help="Se la richiesta arriva dalla miniapp: approvata, il Telegram "
             "passa alla scheda del nuovo socio.",
    )


class CroceviaMiniappTessera(models.AbstractModel):
    _inherit = 'crocevia.miniapp'

    def _importo(self, chiave, standard):
        valore = self.env['ir.config_parameter'].sudo().get_param(
            'crocevia_tesseramento.' + chiave, str(standard))
        try:
            return float(valore)
        except (TypeError, ValueError):
            return float(standard)

    def _quota_tesseramento(self):
        return self._importo('importo_tesseramento', 10)

    # ---------------- la propria tessera ----------------

    @api.model
    def tessera(self, telegram_id):
        """Tessera, mensilita' dell'anno e ricevute di chi chiede.

        Le mensilita' sono solo quelle pagate: i mesi saltati non sono un
        debito (si paga nei mesi in cui si partecipa), quindi la tessera non
        dice "in regola" o "in ritardo".
        """
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        Ricevuta = self.env['crocevia.ricevuta'].sudo()
        ricevute = Ricevuta.search([('partner_id', '=', socio.id)],
                                   order='data desc, id desc', limit=100)
        anno = fields.Date.context_today(self).year
        dell_anno = ricevute.filtered(
            lambda r: (r.mese_riferimento or '').startswith(str(anno)))
        tipi = dict(Ricevuta._fields['tipo'].selection)
        metodi = dict(Ricevuta._fields['metodo'].selection)
        categorie = dict(socio._fields['categoria_socio'].selection)
        # Il riepilogo delle spese dell'anno: per tipo, quante e quanto.
        spese = {}
        for r in ricevute.filtered(lambda r: r.data and r.data.year == anno):
            voce = spese.setdefault(r.tipo, {'tipo': tipi.get(r.tipo, r.tipo), 'quante': 0, 'totale': 0.0})
            voce['quante'] += 1
            voce['totale'] += r.importo
        return {
            'nome': socio.name,
            'numero_socio': socio.numero_socio or False,
            'categoria': categorie.get(socio.categoria_socio, '') or '',
            'data_iscrizione': fields.Date.to_string(socio.data_iscrizione) or False,
            'anno': anno,
            'tesserato': any(r.tipo == 'tesseramento' for r in dell_anno),
            'mensilita': sorted({r.mese_riferimento for r in dell_anno
                                 if r.tipo in ('tesseramento', 'contributo_mensile')}),
            'quota': self._quota_tesseramento(),
            'spese': sorted(spese.values(), key=lambda v: -v['totale']),
            # Quanto costa ogni voce che si potra' pagare dall'app.
            'importi': {
                'obolo_giornaliero': self._importo('importo_obolo', 2),
                'contributo_mensile': self._importo('importo_mensile', 10),
                'contributo_evento': self._importo('importo_evento_default', 3),
                'tesseramento': self._quota_tesseramento(),
            },
            'ricevute': [{
                'id': r.id,
                'numero': r.numero,
                'data': fields.Date.to_string(r.data),
                'tipo': tipi.get(r.tipo, r.tipo),
                # Il codice serve all'app per riconoscere cosa e' gia' pagato
                # (l'obolo di oggi, per esempio); 'tipo' e' quello da mostrare.
                'codice': r.tipo,
                'importo': r.importo,
                'metodo': metodi.get(r.metodo, r.metodo),
                'mese': r.mese_riferimento or False,
            } for r in ricevute],
        }

    @api.model
    def ricevuta_pdf(self, telegram_id, ricevuta_id):
        """Il PDF di una propria ricevuta, che il server manda in chat."""
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        ricevuta = self.env['crocevia.ricevuta'].sudo().browse(int(ricevuta_id)).exists()
        if not ricevuta or ricevuta.partner_id != socio:
            raise UserError(_("Non è una tua ricevuta."))
        pdf, _tipo = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'crocevia_tesseramento.action_report_crocevia_ricevuta', [ricevuta.id])
        nome = (ricevuta.numero or 'ricevuta').replace('/', '-')
        return {'nome_file': f"{nome}.pdf", 'numero': ricevuta.numero,
                'pdf': base64.b64encode(pdf).decode()}

    # ---------------- tesseramento di chi non e' sociə ----------------

    def _richiesta_aperta(self, telegram_id):
        return self.env['crocevia.richiesta.iscrizione'].sudo().search([
            ('telegram_id', '=', str(telegram_id)), ('state', '=', 'nuova'),
        ], limit=1)

    def _dati_richiesta(self, r):
        return {'id': r.id, 'nome': r.nome, 'cognome': r.cognome,
                'data': fields.Datetime.to_string(r.create_date)}

    @api.model
    def stato_iscrizione(self, telegram_id):
        """La richiesta di tesseramento ancora da decidere, se c'e', e la
        quota da pagare."""
        self._controlla_accesso()
        r = self._richiesta_aperta(telegram_id)
        return {'richiesta': self._dati_richiesta(r) if r else False,
                'quota': self._quota_tesseramento()}

    @api.model
    def richiedi_iscrizione(self, telegram_id, valori):
        self._controlla_accesso()
        if not telegram_id:
            raise UserError(_("Non riesco a riconoscerti: riapri l’app."))
        if self._scheda_telegram(telegram_id):
            raise UserError(_("Questo Telegram è già collegato a una scheda: parlane in sede."))
        gia = self._richiesta_aperta(telegram_id)
        if gia:
            return self._dati_richiesta(gia)
        vals = {k: str(valori.get(k) or '').strip() for k in CAMPI_ISCRIZIONE}
        mancanti = [k for k in OBBLIGATORI if not vals[k]]
        if mancanti:
            raise UserError(_("Mancano dei dati obbligatori."))
        vals['codice_fiscale'] = vals['codice_fiscale'].upper()
        vals['provincia'] = vals['provincia'].upper()[:2]
        vals['cap'] = vals['cap'][:5]
        if not CF_RE.match(vals['codice_fiscale']):
            raise UserError(_("Il codice fiscale non sembra giusto: sono 16 lettere e cifre."))
        if not EMAIL_RE.match(vals['email']):
            raise UserError(_("L’indirizzo email non sembra giusto."))
        try:
            nascita = fields.Date.to_date(vals['data_nascita'])
        except ValueError:
            nascita = False
        if not nascita or nascita >= fields.Date.context_today(self):
            raise UserError(_("La data di nascita non sembra giusta."))
        vals.update(data_nascita=nascita, categoria_richiesta='volontario',
                    consenso_privacy=True, telegram_id=str(telegram_id))
        r = self.env['crocevia.richiesta.iscrizione'].sudo().create(
            {k: v or False for k, v in vals.items()})
        r.message_post(body=_("Richiesta arrivata dalla miniapp Telegram."),
                       subtype_xmlid='mail.mt_note')
        return self._dati_richiesta(r)

    def _richiesta_da_decidere(self, richiesta_id):
        r = self.env['crocevia.richiesta.iscrizione'].sudo().browse(int(richiesta_id)).exists()
        if not r or r.state != 'nuova':
            raise UserError(_("Questa richiesta è già stata decisa."))
        return r

    @api.model
    def approva_iscrizione(self, richiesta_id, metodo, da_chi):
        """Il direttivo ha visto il pagamento della quota: nasce la scheda
        socio con il suo numero, il Telegram passa a lei e si registra la
        ricevuta del tesseramento."""
        self._controlla_accesso()
        if metodo not in METODI_APPROVAZIONE:
            raise UserError(_("Metodo di pagamento sconosciuto."))
        r = self._richiesta_da_decidere(richiesta_id)
        if r.telegram_id and self._scheda_telegram(r.telegram_id):
            raise UserError(_("Questo Telegram è già collegato a una scheda: approvala da Odoo."))
        r.action_approva()
        socio = r.partner_id
        oggi = fields.Date.context_today(self)
        socio.write({'telegram_id': r.telegram_id or False,
                     'miniapp_privacy_data': r.create_date})
        ricevuta = self.env['crocevia.ricevuta'].sudo().create({
            'partner_id': socio.id,
            'data': oggi,
            'tipo': 'tesseramento',
            'mese_riferimento': oggi.strftime('%Y-%m'),
            'importo': self._quota_tesseramento(),
            'metodo': metodo,
        })
        r.message_post(body=_("Approvata dalla miniapp da %(chi)s, quota pagata (%(metodo)s): "
                              "ricevuta %(numero)s.", chi=da_chi, metodo=metodo,
                              numero=ricevuta.numero), subtype_xmlid='mail.mt_note')
        return dict(self._dati_socio(socio), telegram_id=r.telegram_id or False,
                    ricevuta=ricevuta.numero)

    @api.model
    def rifiuta_iscrizione(self, richiesta_id, da_chi):
        self._controlla_accesso()
        r = self._richiesta_da_decidere(richiesta_id)
        r.action_rifiuta()
        r.message_post(body=_("Rifiutata dalla miniapp da %s.", da_chi),
                       subtype_xmlid='mail.mt_note')
        return {'telegram_id': r.telegram_id or False, 'nome': f"{r.nome} {r.cognome}"}

    @api.model
    def da_rinnovare(self):
        """Per il promemoria di gennaio: soci attivi con Telegram e senza la
        ricevuta di tesseramento di quest'anno."""
        self._controlla_accesso()
        anno = str(fields.Date.context_today(self).year)
        soci = self.env['res.partner'].sudo().search([
            ('is_socio', '=', True), ('stato_socio', '=', 'attivo'),
            ('telegram_id', '!=', False),
        ])
        pagato = set(self.env['crocevia.ricevuta'].sudo().search([
            ('partner_id', 'in', soci.ids), ('tipo', '=', 'tesseramento'),
            ('mese_riferimento', '=like', anno + '-%'),
        ]).mapped('partner_id').ids)
        return [{'telegram_id': s.telegram_id, 'nome': s.name}
                for s in soci if s.id not in pagato]
