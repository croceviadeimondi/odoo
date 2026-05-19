from odoo import api, fields, models, _


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

    @api.onchange('categoria_socio')
    def _onchange_categoria_socio(self):
        # I soci onorari sono esenti dalla quota: marchiamoli come "membri
        # gratuiti" (campo nativo del modulo membership).
        if self.categoria_socio == 'onorario':
            self.free_member = True

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
            if partner.categoria_socio == 'onorario':
                vals['free_member'] = True
            partner.write(vals)

    def action_cessa_socio(self):
        for partner in self:
            partner.write({
                'stato_socio': 'cessato',
                'data_cessazione': partner.data_cessazione
                    or fields.Date.context_today(partner),
            })
