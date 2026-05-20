from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CroceviaPrestito(models.Model):
    _name = 'crocevia.prestito'
    _description = "Prestito di un bene"
    _inherit = ['mail.thread']
    _order = 'data_prestito desc, id desc'

    bene_id = fields.Many2one(
        'crocevia.bene',
        string="Bene",
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Prestatario",
        required=True,
        tracking=True,
        help="Chi ha preso in prestito il bene. Preferibilmente un socio.",
    )
    data_prestito = fields.Date(
        string="Data prestito",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    data_restituzione_prevista = fields.Date(
        string="Restituzione prevista",
        tracking=True,
        help="Se vuoto, prestito senza scadenza fissata.",
    )
    data_restituzione_effettiva = fields.Date(
        string="Restituito il",
        tracking=True,
        copy=False,
    )
    stato = fields.Selection(
        selection=[
            ('attivo', 'In corso'),
            ('in_ritardo', 'In ritardo'),
            ('restituito', 'Restituito'),
        ],
        compute='_compute_stato',
        store=True,
        string="Stato",
    )
    note = fields.Text(string="Note")

    @api.depends('data_restituzione_effettiva', 'data_restituzione_prevista')
    def _compute_stato(self):
        oggi = fields.Date.context_today(self)
        for p in self:
            if p.data_restituzione_effettiva:
                p.stato = 'restituito'
            elif (p.data_restituzione_prevista
                  and p.data_restituzione_prevista < oggi):
                p.stato = 'in_ritardo'
            else:
                p.stato = 'attivo'

    @api.constrains('bene_id', 'data_restituzione_effettiva')
    def _check_un_prestito_aperto_per_bene(self):
        # Un bene puo' avere al massimo un prestito aperto
        # (data_restituzione_effettiva NULL) per volta.
        for p in self:
            if p.data_restituzione_effettiva:
                continue
            conflitto = self.search([
                ('id', '!=', p.id),
                ('bene_id', '=', p.bene_id.id),
                ('data_restituzione_effettiva', '=', False),
            ], limit=1)
            if conflitto:
                raise ValidationError(_(
                    "Il bene '%(bene)s' e' gia' in prestito a "
                    "%(partner)s dal %(data)s. Restituire quel prestito "
                    "prima di aprirne uno nuovo."
                ) % {
                    'bene': p.bene_id.name,
                    'partner': conflitto.partner_id.display_name,
                    'data': conflitto.data_prestito,
                })

    def action_restituisci(self):
        for p in self:
            if p.data_restituzione_effettiva:
                continue
            p.data_restituzione_effettiva = fields.Date.context_today(p)

    @api.depends('bene_id', 'partner_id', 'data_prestito')
    def _compute_display_name(self):
        for p in self:
            p.display_name = "%s a %s (%s)" % (
                p.bene_id.name or '?',
                p.partner_id.display_name or '?',
                p.data_prestito or '?',
            )
