from odoo import fields, models


class CroceviaVerbale(models.Model):
    _name = 'crocevia.verbale'
    _description = "Verbale"
    _inherit = ['mail.thread']
    _order = 'data desc, id desc'

    name = fields.Char(string="Oggetto", required=True, tracking=True)
    data = fields.Date(
        string="Data",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    tipo = fields.Selection(
        selection=[
            ('assemblea_soci', 'Assemblea soci'),
            ('riunione_direttivo', 'Riunione direttivo'),
        ],
        string="Tipo",
        required=True,
        default='assemblea_soci',
        tracking=True,
    )
    note = fields.Text(string="Note / sintesi")
    documento = fields.Binary(
        string="Verbale (file)",
        attachment=True,
        help="PDF / DOCX del verbale firmato.",
    )
    documento_filename = fields.Char(string="Nome file")
