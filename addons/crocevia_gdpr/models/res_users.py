from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    gdpr_accettata = fields.Boolean(
        string="Informativa GDPR accettata",
        default=False,
        copy=False,
    )
    gdpr_accettata_il = fields.Datetime(
        string="GDPR accettata il",
        readonly=True,
        copy=False,
    )

    @property
    def SELF_READABLE_FIELDS(self):
        # Permette all'utente di leggere il proprio stato di accettazione.
        return super().SELF_READABLE_FIELDS + ['gdpr_accettata', 'gdpr_accettata_il']
