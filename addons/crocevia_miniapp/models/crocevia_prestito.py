from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CroceviaPrestito(models.Model):
    _inherit = 'crocevia.prestito'

    # Chi amministra la biblioteca puo' segnare che un bene l'ha preso
    # qualcuno senza scheda in Odoo (un ospite, un amico di un socio): basta
    # il nome. O la scheda o il nome, almeno uno dei due.
    partner_id = fields.Many2one(required=False)
    prestatario_libero = fields.Char(
        string="Preso da (nome)",
        tracking=True,
        help="Per chi non ha una scheda in Odoo: il nome di chi ha preso il bene.",
    )

    @api.constrains('partner_id', 'prestatario_libero')
    def _check_prestatario(self):
        for p in self:
            if not p.partner_id and not (p.prestatario_libero or '').strip():
                raise ValidationError(_("Serve chi ha preso il bene: una scheda o almeno un nome."))

    @api.depends('bene_id', 'partner_id', 'prestatario_libero', 'data_prestito')
    def _compute_display_name(self):
        for p in self:
            p.display_name = "%s a %s (%s)" % (
                p.bene_id.name or '?',
                p.partner_id.display_name or p.prestatario_libero or '?',
                p.data_prestito or '?',
            )
