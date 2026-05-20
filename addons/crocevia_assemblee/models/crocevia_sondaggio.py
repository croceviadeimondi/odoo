"""
Sondaggi per scegliere la data della prossima assemblea/riunione.

Tre modelli:
- `crocevia.sondaggio`         oggetto sondaggio (testata)
- `crocevia.sondaggio.data`    una delle date proposte (n righe per
                                sondaggio)
- `crocevia.sondaggio.voto`    voto di un socio per una specifica
                                data proposta (n righe per sondaggio)

Workflow:
1. Direttivo crea sondaggio con titolo, lista date proposte e data di
   chiusura (default: oggi + 4 giorni).
2. Sondaggio in stato `bozza` -> click "Pubblica" -> stato `aperto`.
   In futuro: a questo punto si chiamera' Telegram per pubblicare il
   poll nel canale soci. Per ora il sondaggio e' votabile solo via UI
   Odoo.
3. I soci votano (un solo voto per persona; rivotare aggiorna il voto
   precedente).
4. Cron orario chiude i sondaggi con `data_chiusura <= now`. Calcola
   la data vincente (piu' voti; in caso di parita' la prima in ordine
   temporale). In futuro: chiama Telegram per chiudere il poll e
   manda email a soci attivi. Per ora logga e basta.

Niente reportistica complicata: il direttivo vede direttamente in
Odoo il conteggio per data sul form del sondaggio.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class CroceviaSondaggio(models.Model):
    _name = 'crocevia.sondaggio'
    _description = "Sondaggio per data assemblea"
    _inherit = ['mail.thread']
    _order = 'data_creazione desc, id desc'

    name = fields.Char(string="Titolo", required=True, tracking=True)
    descrizione = fields.Text(string="Descrizione")
    data_creazione = fields.Datetime(
        string="Creato il",
        default=fields.Datetime.now,
        readonly=True,
    )
    data_chiusura = fields.Datetime(
        string="Chiusura prevista",
        required=True,
        tracking=True,
        help="Quando il cron chiude automaticamente il sondaggio. "
             "Default: data creazione + 4 giorni.",
    )
    stato = fields.Selection(
        selection=[
            ('bozza', 'Bozza'),
            ('aperto', 'Aperto'),
            ('chiuso', 'Chiuso'),
            ('annullato', 'Annullato'),
        ],
        string="Stato",
        default='bozza',
        required=True,
        tracking=True,
    )

    data_proposta_ids = fields.One2many(
        'crocevia.sondaggio.data', 'sondaggio_id',
        string="Date proposte",
    )
    voto_ids = fields.One2many(
        'crocevia.sondaggio.voto', 'sondaggio_id',
        string="Voti",
    )
    num_voti_totali = fields.Integer(
        string="Voti totali",
        compute='_compute_num_voti_totali',
    )
    data_vincente = fields.Date(
        string="Data vincente",
        readonly=True,
        copy=False,
        tracking=True,
        help="Popolato automaticamente alla chiusura.",
    )

    # Mock per integrazione esterna (verranno usati quando bot+SMTP attivi)
    telegram_message_id = fields.Char(
        string="ID messaggio Telegram",
        readonly=True,
        help="Mock: riempito dall'integrazione Telegram quando attiva.",
    )
    email_inviata = fields.Boolean(
        string="Email risultato inviata",
        readonly=True,
        copy=False,
    )

    # ----------------- defaults -----------------

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'data_chiusura' in fields_list and not defaults.get('data_chiusura'):
            defaults['data_chiusura'] = fields.Datetime.now() + timedelta(days=4)
        return defaults

    # ----------------- computed -----------------

    @api.depends('voto_ids')
    def _compute_num_voti_totali(self):
        for s in self:
            s.num_voti_totali = len(s.voto_ids)

    # ----------------- vincoli -----------------

    @api.constrains('data_chiusura', 'data_creazione')
    def _check_chiusura_futura(self):
        for s in self:
            if s.stato == 'bozza' and s.data_chiusura and s.data_chiusura <= fields.Datetime.now():
                raise ValidationError(_(
                    "La data di chiusura deve essere nel futuro "
                    "(ora: %s, chiusura: %s)."
                ) % (fields.Datetime.now(), s.data_chiusura))

    # ----------------- workflow -----------------

    def action_pubblica(self):
        """Da 'bozza' -> 'aperto'. In futuro pubblica il poll su Telegram."""
        for s in self:
            if s.stato != 'bozza':
                raise UserError(_("Solo i sondaggi in bozza si possono pubblicare."))
            if not s.data_proposta_ids:
                raise UserError(_(
                    "Aggiungi almeno una data proposta prima di pubblicare."))
            s.stato = 'aperto'
            s._invia_telegram_poll_mock()
            s.message_post(body=_("Sondaggio pubblicato. Voto aperto fino a %s.") % s.data_chiusura)

    def action_annulla(self):
        for s in self:
            if s.stato == 'chiuso':
                raise UserError(_("Un sondaggio chiuso non si annulla, eventualmente cancella i voti."))
            s.stato = 'annullato'
            s.message_post(body=_("Sondaggio annullato."))

    def action_chiudi_manuale(self):
        """Chiusura forzata anticipata dal direttivo."""
        for s in self:
            if s.stato != 'aperto':
                raise UserError(_("Solo i sondaggi aperti si possono chiudere."))
            s._chiudi()

    # ----------------- chiusura (interno) -----------------

    def _chiudi(self):
        """Calcola la data vincente, set stato chiuso, mock notifiche."""
        for s in self:
            # Conta voti per data; in caso di parita' vince la piu' vicina
            # nel tempo (la prima in ordine ascendente di data).
            conteggi = sorted(
                [(d, len(d.voto_ids)) for d in s.data_proposta_ids],
                key=lambda x: (-x[1], x[0].data),
            )
            if conteggi and conteggi[0][1] > 0:
                s.data_vincente = conteggi[0][0].data
            s.stato = 'chiuso'
            s._chiudi_telegram_poll_mock()
            s._invia_email_risultato_mock()
            risultato = (
                _("Data scelta: %s (%d voti)") % (s.data_vincente, conteggi[0][1])
                if s.data_vincente
                else _("Nessun voto ricevuto, sondaggio chiuso senza data vincente.")
            )
            s.message_post(body=risultato)

    @api.model
    def cron_chiudi_scaduti(self):
        """Eseguito ogni ora dal cron. Chiude i sondaggi scaduti."""
        scaduti = self.search([
            ('stato', '=', 'aperto'),
            ('data_chiusura', '<=', fields.Datetime.now()),
        ])
        if scaduti:
            _logger.info("crocevia_assemblee: chiudo %d sondaggi scaduti", len(scaduti))
            scaduti._chiudi()

    # ----------------- integrazione esterna (mock) -----------------

    def _invia_telegram_poll_mock(self):
        """STUB: in futuro chiamera' Telegram Bot API per creare il poll
        nel canale soci. Per ora logga e basta."""
        for s in self:
            _logger.info(
                "TELEGRAM MOCK: pubblicherei poll '%s' con %d opzioni "
                "(scadenza %s). Per attivare, configurare i parametri "
                "`crocevia.telegram_bot_token` e `crocevia.telegram_chat_id_soci` "
                "+ implementare l'invio.",
                s.name, len(s.data_proposta_ids), s.data_chiusura,
            )

    def _chiudi_telegram_poll_mock(self):
        for s in self:
            _logger.info(
                "TELEGRAM MOCK: chiuderei il poll del sondaggio '%s' "
                "(message_id=%s).",
                s.name, s.telegram_message_id or 'n/a',
            )

    def _invia_email_risultato_mock(self):
        """STUB: in futuro creera' `mail.mail` con template e recipient
        list = soci attivi dell'anno. Per ora logga e basta."""
        for s in self:
            soci_attivi = self.env['res.partner'].search([
                ('is_socio', '=', True),
                ('stato_socio', '=', 'attivo'),
            ])
            _logger.info(
                "EMAIL MOCK: invierei a %d soci attivi l'esito del "
                "sondaggio '%s' (data vincente: %s).",
                len(soci_attivi), s.name, s.data_vincente or 'nessuna',
            )
            s.email_inviata = True


class CroceviaSondaggioData(models.Model):
    """Una delle date proposte nel sondaggio."""

    _name = 'crocevia.sondaggio.data'
    _description = "Data proposta in un sondaggio assemblea"
    _order = 'data asc'

    sondaggio_id = fields.Many2one(
        'crocevia.sondaggio',
        string="Sondaggio",
        required=True,
        ondelete='cascade',
    )
    data = fields.Date(string="Data", required=True)
    note = fields.Char(
        string="Nota",
        help="Es. 'sera in sede', 'pomeriggio online via Meet', ecc.",
    )
    voto_ids = fields.One2many(
        'crocevia.sondaggio.voto', 'data_proposta_id',
        string="Voti")
    num_voti = fields.Integer(
        string="N. voti",
        compute='_compute_num_voti',
        store=False,
    )

    @api.depends('voto_ids')
    def _compute_num_voti(self):
        for d in self:
            d.num_voti = len(d.voto_ids)

    @api.depends('data', 'note', 'num_voti')
    def _compute_display_name(self):
        for d in self:
            base = d.data.strftime('%d/%m/%Y') if d.data else '?'
            if d.note:
                base = "%s (%s)" % (base, d.note)
            d.display_name = "%s - %d voti" % (base, d.num_voti)


class CroceviaSondaggioVoto(models.Model):
    """Voto di un socio per una specifica data proposta.

    Vincolo: un socio puo' votare una sola data per sondaggio
    (`(sondaggio_id, partner_id)` unique).
    """

    _name = 'crocevia.sondaggio.voto'
    _description = "Voto in un sondaggio assemblea"
    _order = 'create_date desc, id desc'

    sondaggio_id = fields.Many2one(
        'crocevia.sondaggio',
        string="Sondaggio",
        required=True,
        ondelete='cascade',
        index=True,
    )
    data_proposta_id = fields.Many2one(
        'crocevia.sondaggio.data',
        string="Data votata",
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Socio",
        required=True,
        domain="[('is_socio', '=', True)]",
        index=True,
    )

    _sql_constraints = [
        ('unique_voto_per_socio_per_sondaggio',
         'UNIQUE(sondaggio_id, partner_id)',
         "Ogni socio puo' votare una sola data per sondaggio. "
         "Per cambiare voto, modifica quello esistente."),
    ]

    @api.constrains('sondaggio_id', 'data_proposta_id')
    def _check_data_appartiene_al_sondaggio(self):
        for v in self:
            if v.data_proposta_id.sondaggio_id != v.sondaggio_id:
                raise ValidationError(_(
                    "La data votata non appartiene a questo sondaggio."))

    @api.constrains('sondaggio_id')
    def _check_sondaggio_aperto(self):
        for v in self:
            if v.sondaggio_id.stato != 'aperto':
                raise ValidationError(_(
                    "Si vota solo nei sondaggi in stato 'Aperto'. "
                    "Questo e' in stato '%s'."
                ) % dict(v.sondaggio_id._fields['stato'].selection).get(
                    v.sondaggio_id.stato, v.sondaggio_id.stato))
