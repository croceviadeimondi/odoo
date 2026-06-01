from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CroceviaAttivitaVolontariato(models.Model):
    _name = 'crocevia.attivita.volontariato'
    _description = "Ora di attività volontaria prestata"
    _inherit = ['mail.thread']
    _order = 'data desc, id desc'

    partner_id = fields.Many2one(
        'res.partner',
        string="Volontario",
        required=True,
        tracking=True,
        index=True,
        domain=[('is_volontario', '=', True)],
        ondelete='restrict',
    )
    data = fields.Date(
        string="Data",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    ore = fields.Float(
        string="Ore prestate",
        required=True,
        tracking=True,
        help="Ore (frazionarie OK, es. 2.5 = 2 ore e mezza).",
    )
    attivita = fields.Char(
        string="Attività svolta",
        required=True,
        help="Es. 'Allestimento stand', 'Accoglienza ospiti', "
             "'Conduzione laboratorio'.",
    )
    note = fields.Text(string="Note")
    polizza = fields.Char(
        string="Polizza al momento",
        help="Numero polizza assicurativa al momento dell'attività "
             "(se diversa dalla polizza di default sulla scheda).",
    )
    project_id = fields.Many2one(
        'project.project',
        string="Progetto",
        help="Progetto/evento a cui si riferisce l'attività "
             "(opzionale, utile per rendicontazione bandi).",
    )
    sede_id = fields.Many2one(
        'crocevia.sede',
        string="Sede",
        help="Sede dove l'attività è stata svolta.",
    )

    @api.constrains('ore')
    def _check_ore_positive(self):
        for a in self:
            if a.ore <= 0:
                raise ValidationError(_(
                    "Le ore prestate devono essere maggiori di zero."
                ))

    @api.depends('partner_id', 'data', 'ore', 'attivita')
    def _compute_display_name(self):
        for a in self:
            partner = a.partner_id.display_name or '?'
            data = a.data or '?'
            a.display_name = "%s - %s (%sh) - %s" % (
                partner, data, a.ore, a.attivita or '')
