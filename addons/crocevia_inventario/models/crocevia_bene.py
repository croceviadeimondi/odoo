from odoo import api, fields, models, _


CATEGORIA_BENE_SELECTION = [
    ('gioco_da_tavolo', 'Gioco da tavolo'),
    ('gioco_di_ruolo', 'Gioco di ruolo'),
    ('manuale', 'Manuale'),
    ('libro', 'Libro'),
    ('altro', 'Altro'),
]


class CroceviaBene(models.Model):
    _name = 'crocevia.bene'
    _description = "Bene dell'inventario"
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(string="Titolo", required=True, tracking=True)
    categoria = fields.Selection(
        selection=CATEGORIA_BENE_SELECTION,
        string="Categoria",
        required=True,
        default='altro',
        tracking=True,
    )
    sede_id = fields.Many2one(
        'crocevia.sede',
        string="Sede",
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True,
    )
    codice_interno = fields.Char(
        string="Codice interno",
        index=True,
        copy=False,
        help="Codice univoco per etichette/inventario (es. BTL-001).",
    )
    genere_ids = fields.Many2many(
        'crocevia.bene.genere',
        string="Generi",
        help="Generi/collane (Romanzi, Fumetti, Manga, Biografie...). "
             "Un bene puo' averne piu' di uno. Validi anche per i giochi.",
    )
    sistema_id = fields.Many2one(
        'crocevia.bene.sistema',
        string="Sistema di gioco",
        index=True,
        help="Per i giochi di ruolo: il sistema (D&D 5e, Pathfinder, ...).",
    )
    autore = fields.Char(string="Autore")
    editore = fields.Char(string="Editore")
    anno_pubblicazione = fields.Integer(string="Anno pubblicazione")
    isbn = fields.Char(string="ISBN", help="Per i libri")
    valore_stimato = fields.Monetary(string="Valore stimato")
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    note = fields.Text(string="Note")
    active = fields.Boolean(default=True)

    # ----------------- segnalazione bene mancante -----------------
    mancante = fields.Boolean(
        string="Mancante",
        default=False,
        tracking=True,
        help="Segnala che il bene risulta mancante / non reperibile.",
    )
    nota_mancanza = fields.Text(
        string="Nota sulla mancanza",
        help="Dettagli sulla mancanza (dove dovrebbe essere, chi l'ha "
             "cercato, ecc.).",
    )
    stato_bene = fields.Selection(
        selection=[
            ('disponibile', 'Disponibile'),
            ('in_prestito', 'In prestito'),
            ('mancante', 'Mancante'),
        ],
        string="Stato",
        compute='_compute_stato_bene',
        store=True,
        help="Mancante (segnalato) ha priorita'; poi In prestito (prestito "
             "aperto); altrimenti Disponibile.",
    )

    proprietario_id = fields.Many2one(
        'res.partner',
        string="Proprietario",
        tracking=True,
        index=True,
        help=(
            "Se il bene appartiene a un socio o all'associazione (come "
            "partner), collegalo qui. Per proprietari non a sistema usa "
            "'Proprietario (testo)'."
        ),
    )
    proprietario_libero = fields.Char(
        string="Proprietario (testo)",
        tracking=True,
        help=(
            "Da usare quando il proprietario non e' un partner gia' a "
            "sistema (es. soprannomi, ex-soci, 'Gruppone', 'sconosciuto'). "
            "Ignorato se 'Proprietario' e' valorizzato."
        ),
    )
    proprietario_display = fields.Char(
        string="Proprietario (visualizzato)",
        compute='_compute_proprietario_display',
        store=True,
    )

    @api.depends('proprietario_id', 'proprietario_libero')
    def _compute_proprietario_display(self):
        for bene in self:
            if bene.proprietario_id:
                bene.proprietario_display = bene.proprietario_id.display_name
            elif bene.proprietario_libero:
                bene.proprietario_display = bene.proprietario_libero
            else:
                bene.proprietario_display = False

    prestito_ids = fields.One2many(
        'crocevia.prestito', 'bene_id', string="Storico prestiti")
    prestito_corrente_id = fields.Many2one(
        'crocevia.prestito',
        compute='_compute_prestito_corrente',
        store=True,
        string="Prestito in corso",
    )
    in_prestito = fields.Boolean(
        compute='_compute_prestito_corrente',
        store=True,
        index=True,
        string="In prestito",
    )
    prestatario_id = fields.Many2one(
        'res.partner',
        compute='_compute_prestito_corrente',
        store=True,
        string="Attualmente da",
    )

    @api.depends('prestito_ids', 'prestito_ids.data_restituzione_effettiva')
    def _compute_prestito_corrente(self):
        for bene in self:
            aperti = bene.prestito_ids.filtered(
                lambda p: not p.data_restituzione_effettiva)
            corrente = aperti[:1]
            bene.prestito_corrente_id = corrente.id if corrente else False
            bene.in_prestito = bool(corrente)
            bene.prestatario_id = corrente.partner_id.id if corrente else False

    def action_apri_prestito(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Nuovo prestito di %s") % self.name,
            'res_model': 'crocevia.prestito',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bene_id': self.id,
            },
        }

    def action_restituisci_corrente(self):
        self.ensure_one()
        if self.prestito_corrente_id:
            self.prestito_corrente_id.action_restituisci()

    # ----------------- segnalazione bene mancante -----------------

    @api.depends('mancante', 'in_prestito')
    def _compute_stato_bene(self):
        for bene in self:
            if bene.mancante:
                bene.stato_bene = 'mancante'
            elif bene.in_prestito:
                bene.stato_bene = 'in_prestito'
            else:
                bene.stato_bene = 'disponibile'

    def action_segnala_mancante(self):
        for bene in self:
            bene.mancante = True
            bene.message_post(body=_("Segnalato come MANCANTE."))

    def action_segna_disponibile(self):
        for bene in self:
            bene.mancante = False
            bene.message_post(body=_("Segnalato di nuovo come disponibile."))


class CroceviaBeneGenere(models.Model):
    _name = 'crocevia.bene.genere'
    _description = "Genere di un bene (libro, gioco...)"
    _order = 'name'

    name = fields.Char(string="Genere", required=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', "Questo genere esiste gia'."),
    ]


class CroceviaBeneSistema(models.Model):
    _name = 'crocevia.bene.sistema'
    _description = "Sistema di gioco (per i giochi di ruolo)"
    _order = 'name'

    name = fields.Char(string="Sistema", required=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', "Questo sistema esiste gia'."),
    ]
