from odoo import api, fields, models


class CroceviaSede(models.Model):
    _name = 'crocevia.sede'
    _description = "Sede del Crocevia"
    _order = 'citta, id'

    citta = fields.Char(string="Città", required=True, index=True)
    via = fields.Char(string="Via")
    civico = fields.Char(string="N. civico")
    cap = fields.Char(string="CAP", size=5)
    provincia = fields.Char(string="Provincia", size=2)
    referente_id = fields.Many2one(
        'res.partner',
        string="Referente di sede",
        help="Persona di riferimento per questa sede, "
             "preferibilmente un socio del direttivo.",
    )
    is_sede_legale = fields.Boolean(
        string="Sede legale",
        help="La sede legale dell'APS dichiarata nello statuto. "
             "Idealmente una sola sede ha questo flag attivo.",
    )
    note = fields.Text(string="Note")
    active = fields.Boolean(default=True)

    bene_ids = fields.One2many(
        'crocevia.bene', 'sede_id', string="Beni in sede")
    bene_count = fields.Integer(
        compute='_compute_bene_count', string="N. beni")

    @api.depends('bene_ids')
    def _compute_bene_count(self):
        for sede in self:
            sede.bene_count = len(sede.bene_ids)

    @api.depends('citta', 'via', 'civico')
    def _compute_display_name(self):
        for s in self:
            if s.via:
                indirizzo = s.via + ((' ' + s.civico) if s.civico else '')
                s.display_name = "%s - %s" % (s.citta or '?', indirizzo)
            else:
                s.display_name = s.citta or '?'

    def action_apri_beni(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Beni in %s" % (self.citta or 'sede'),
            'res_model': 'crocevia.bene',
            'view_mode': 'list,form',
            'domain': [('sede_id', '=', self.id)],
            'context': {'default_sede_id': self.id},
        }
