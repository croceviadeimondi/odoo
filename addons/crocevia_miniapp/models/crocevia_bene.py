from odoo import api, fields, models


class CroceviaBene(models.Model):
    _inherit = 'crocevia.bene'

    # Quante volte e' stato preso in prestito, da sempre. La biblioteca
    # dell'app mette in cima i beni piu' presi: e' il modo piu' semplice di
    # far trovare subito quello che interessa a tanti.
    numero_prestiti = fields.Integer(
        string="Volte in prestito",
        compute='_compute_numero_prestiti',
        store=True,
        index=True,
    )

    @api.depends('prestito_ids')
    def _compute_numero_prestiti(self):
        for bene in self:
            bene.numero_prestiti = len(bene.prestito_ids)
