from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    telegram_id = fields.Char(
        string="Telegram ID",
        copy=False,
        index=True,
        tracking=True,
        help="User id numerico di Telegram, scritto dalla miniapp quando lo "
             "staff conferma il socio. Si puo' correggere a mano.",
    )
    miniapp_privacy_data = fields.Datetime(
        string="Informativa accettata (miniapp)",
        copy=False,
        help="Quando il socio ha accettato l'informativa privacy "
             "registrandosi dalla miniapp Telegram.",
    )

    miniapp_provvisorio = fields.Boolean(
        string="Registrazione da confermare",
        tracking=True,
        help="Si e' registratə dalla miniapp e la sta gia' usando, ma il "
             "direttivo non ha ancora confermato che sia sociə.",
    )
    admin_miniapp = fields.Boolean(
        string="Amministra la biblioteca",
        tracking=True,
        help="Dalla miniapp vede tutti i prestiti in corso, li prolunga e li "
             "chiude a mano. Chi sta nel gruppo Telegram del direttivo lo e' "
             "gia' senza spunta.",
    )

    _sql_constraints = [
        ('telegram_id_unico', 'unique(telegram_id)',
         "Questo Telegram e' gia' collegato a un'altra scheda."),
    ]

    @api.model
    def _normalizza_telegram(self, vals):
        # Una stringa vuota non e' NULL: due schede "svuotate" a mano
        # farebbero scattare il vincolo di unicita'.
        if 'telegram_id' in vals:
            valore = (vals['telegram_id'] or '').strip()
            vals['telegram_id'] = valore or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._normalizza_telegram(v) for v in vals_list])

    def write(self, vals):
        return super().write(self._normalizza_telegram(vals))
