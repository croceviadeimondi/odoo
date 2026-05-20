from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_volontario = fields.Boolean(
        string="È volontario",
        index=True,
        help="Iscritto al libro dei volontari (art. 17 D.Lgs 117/2017). "
             "Volontario e socio sono due cose distinte: si può essere "
             "volontari senza essere soci.",
    )
    data_inizio_volontariato = fields.Date(
        string="Inizio volontariato",
        tracking=True,
    )
    data_fine_volontariato = fields.Date(
        string="Fine volontariato",
        tracking=True,
    )
    polizza_volontariato = fields.Char(
        string="Polizza assicurativa volontari",
        help="Estremi della polizza che copre il volontario "
             "(numero, compagnia, scadenza).",
    )
    attivita_volontariato_descrizione = fields.Text(
        string="Mansioni svolte",
        help="Descrizione delle attività svolte come volontario.",
    )
    attivita_volontariato_ids = fields.One2many(
        'crocevia.attivita.volontariato',
        'partner_id',
        string="Ore prestate",
    )
    ore_volontariato_anno_corrente = fields.Float(
        string="Ore anno corrente",
        compute='_compute_ore_volontariato_anno_corrente',
    )

    @api.depends('attivita_volontariato_ids.ore',
                 'attivita_volontariato_ids.data')
    def _compute_ore_volontariato_anno_corrente(self):
        oggi = fields.Date.context_today(self)
        anno = oggi.year
        for p in self:
            attivita_anno = p.attivita_volontariato_ids.filtered(
                lambda a: a.data and a.data.year == anno)
            p.ore_volontariato_anno_corrente = sum(attivita_anno.mapped('ore'))
