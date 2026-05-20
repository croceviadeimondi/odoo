from odoo import api, fields, models


CATEGORIA_SOCIO_SELECTION = [
    ('amministrativo', 'Amministrativo'),
    ('volontario', 'Volontario'),
    ('onorario', 'Onorario'),
    ('direttivo', 'Direttivo'),
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

    def action_registra_quota_annuale(self):
        """Apre wizard quota annuale (10 EUR di default, copre 1a mensilita')."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registra quota annuale',
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
