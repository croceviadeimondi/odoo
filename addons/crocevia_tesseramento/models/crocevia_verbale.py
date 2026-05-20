from odoo import fields, models


class CroceviaVerbale(models.Model):
    """Atto formale o resoconto informale di un'assemblea o riunione del
    direttivo. Il `tipo` distingue i 3 casi:
    - `assemblea_soci`: verbale ufficiale dell'assemblea, firmato (PDF
      caricato in `documento`).
    - `riunione_direttivo`: verbale ufficiale del direttivo, idem.
    - `resoconto_informale`: nota di lavoro non firmata (es. brief di
      una chiacchierata o di un incontro online), con corpo testuale
      direttamente nel campo `contenuto`, senza obbligo di pdf allegato.
    """

    _name = 'crocevia.verbale'
    _description = "Verbale o resoconto di assemblea"
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
            ('assemblea_soci', 'Verbale assemblea soci'),
            ('riunione_direttivo', 'Verbale riunione direttivo'),
            ('resoconto_informale', 'Resoconto informale'),
        ],
        string="Tipo",
        required=True,
        default='assemblea_soci',
        tracking=True,
    )
    note = fields.Text(string="Note / sintesi")
    contenuto = fields.Text(
        string="Contenuto",
        help="Testo del resoconto informale (markdown supportato in UI). "
             "Usato quando non c'e' un PDF firmato da allegare.",
    )
    documento = fields.Binary(
        string="Verbale (file)",
        attachment=True,
        help="PDF / DOCX del verbale firmato. Tipico per i tipi "
             "'Verbale assemblea' e 'Verbale direttivo'.",
    )
    documento_filename = fields.Char(string="Nome file")
