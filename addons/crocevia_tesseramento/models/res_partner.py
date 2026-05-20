from odoo import api, fields, models


CATEGORIA_SOCIO_SELECTION = [
    ('amministrativo', 'Amministrativo'),
    ('volontario', 'Volontario'),
    ('onorario', 'Onorario'),
    ('direttivo', 'Direttivo'),
]

STATO_CIVILE_SELECTION = [
    ('celibe', 'Celibe/Nubile'),
    ('coniugato', 'Coniugato/a'),
    ('divorziato', 'Divorziato/a'),
    ('vedovo', 'Vedovo/a'),
    ('altro', 'Altro / non dichiarato'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_socio = fields.Boolean(
        string="È socio",
        index=True,
        help="Indica che questo contatto è un socio del Crocevia (o ex socio).",
    )
    numero_socio = fields.Char(
        string="Numero socio",
        copy=False,
        readonly=True,
        index=True,
        help="Numero progressivo del libro soci. Viene assegnato "
             "automaticamente all'attivazione del socio.",
    )
    categoria_socio = fields.Selection(
        selection=CATEGORIA_SOCIO_SELECTION,
        string="Categoria socio",
    )
    stato_socio = fields.Selection(
        selection=[
            ('richiesta', 'Richiesta'),
            ('attivo', 'Attivo'),
            ('cessato', 'Cessato'),
        ],
        string="Stato socio",
        default='richiesta',
        tracking=True,
    )
    data_iscrizione = fields.Date(string="Data iscrizione")
    data_cessazione = fields.Date(string="Data cessazione")

    # Anagrafica privata del socio (per libro soci + ricevute + RUNTS).
    # Sono campi del Crocevia, non standard in res.partner.
    data_nascita = fields.Date(string="Data di nascita")
    luogo_nascita = fields.Char(string="Luogo di nascita")
    codice_fiscale = fields.Char(
        string="Codice fiscale",
        size=16,
        index=True,
        help="Codice fiscale di persona fisica (16 caratteri). "
             "Viene normalizzato in maiuscolo via constraint.",
    )
    stato_civile = fields.Selection(
        selection=STATO_CIVILE_SELECTION,
        string="Stato civile",
    )

    @api.constrains('codice_fiscale')
    def _check_codice_fiscale(self):
        for p in self:
            if p.codice_fiscale:
                # Normalizza in maiuscolo (idempotente)
                cf = p.codice_fiscale.strip().upper()
                if cf != p.codice_fiscale:
                    p.codice_fiscale = cf
    carica_ids = fields.One2many(
        'crocevia.carica', 'partner_id', string="Cariche direttive")
    ricevuta_ids = fields.One2many(
        'crocevia.ricevuta', 'partner_id', string="Ricevute")
    carica_attuale = fields.Char(
        string="Carica in corso",
        compute='_compute_carica_attuale',
        store=True,
    )

    @api.depends('carica_ids.is_attuale', 'carica_ids.ruolo')
    def _compute_carica_attuale(self):
        ruolo_dict = dict(self.env['crocevia.carica']._fields['ruolo'].selection)
        for partner in self:
            cariche = partner.carica_ids.filtered(lambda c: c.is_attuale)
            partner.carica_attuale = ", ".join(
                ruolo_dict.get(c.ruolo, c.ruolo) for c in cariche
            ) or False

    def action_attiva_socio(self):
        Sequence = self.env['ir.sequence']
        for partner in self:
            if partner.stato_socio == 'attivo':
                continue
            vals = {
                'is_socio': True,
                'stato_socio': 'attivo',
                'data_iscrizione': partner.data_iscrizione
                    or fields.Date.context_today(partner),
            }
            if not partner.numero_socio:
                vals['numero_socio'] = Sequence.next_by_code(
                    'crocevia.numero.socio')
            partner.write(vals)

    def action_cessa_socio(self):
        for partner in self:
            partner.write({
                'stato_socio': 'cessato',
                'data_cessazione': partner.data_cessazione
                    or fields.Date.context_today(partner),
            })

    # ----------------- ricevute: bottoni quick-action -----------------

    def action_registra_obolo(self):
        """Obolo da 2 EUR (fisso), in contanti, registrato in 1 click."""
        self.ensure_one()
        importo = self._param_importo('crocevia_tesseramento.importo_obolo', 2.0)
        ricevuta = self.env['crocevia.ricevuta'].create({
            'partner_id': self.id,
            'tipo': 'obolo_giornaliero',
            'importo': importo,
            'metodo': 'contanti',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ricevuta obolo',
            'res_model': 'crocevia.ricevuta',
            'res_id': ricevuta.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_registra_mensilita(self):
        """Apre wizard mensilita' (mese e importo modificabili)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registra contributo mensile',
            'res_model': 'crocevia.ricevuta.mensilita.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.id},
        }

    def action_registra_evento(self):
        """Apre wizard evento (importo modificabile, default 3 EUR)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registra contributo evento',
            'res_model': 'crocevia.ricevuta.evento.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.id},
        }

    def action_registra_tesseramento(self):
        """Apre wizard tesseramento (10 EUR di default, copre 1a mensilita')."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registra tesseramento',
            'res_model': 'crocevia.ricevuta.quota.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.id},
        }

    def _param_importo(self, key, fallback):
        """Legge un importo dai parametri di sistema con fallback float."""
        try:
            return float(self.env['ir.config_parameter'].sudo()
                         .get_param(key, str(fallback)))
        except (TypeError, ValueError):
            return float(fallback)

    def action_mostra_qr_bonifico(self):
        """Apre wizard col QR EPC per fare un bonifico SEPA precompilato
        al conto del crocevia (importo e causale modificabili al volo)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'QR bonifico - %s' % self.name,
            'res_model': 'crocevia.qr.bonifico.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.id},
        }
