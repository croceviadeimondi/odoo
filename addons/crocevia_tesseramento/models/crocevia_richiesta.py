from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CroceviaRichiestaIscrizione(models.Model):
    _name = 'crocevia.richiesta.iscrizione'
    _description = "Richiesta di iscrizione"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string="Riferimento",
        compute='_compute_name',
        store=True,
    )

    # Anagrafica
    nome = fields.Char(string="Nome", required=True, tracking=True)
    cognome = fields.Char(string="Cognome", required=True, tracking=True)
    data_nascita = fields.Date(string="Data di nascita")
    luogo_nascita = fields.Char(string="Luogo di nascita")
    codice_fiscale = fields.Char(string="Codice fiscale", size=16)

    # Contatti
    email = fields.Char(string="Email", required=True, tracking=True)
    telefono = fields.Char(string="Telefono")
    indirizzo = fields.Char(string="Indirizzo")
    cap = fields.Char(string="CAP", size=5)
    citta = fields.Char(string="Città")
    provincia = fields.Char(string="Provincia", size=2)

    # Richiesta
    categoria_richiesta = fields.Selection(
        selection=[
            ('volontario', 'Volontario'),
            ('amministrativo', 'Amministrativo'),
        ],
        string="Categoria richiesta",
        default='volontario',
        help="Le categorie Direttivo e Onorario non sono richiedibili online: "
             "vengono assegnate per delibera del direttivo / assemblea.",
    )
    messaggio = fields.Text(string="Messaggio del richiedente")
    consenso_privacy = fields.Boolean(
        string="Consenso al trattamento dei dati",
        required=True,
    )

    # Workflow
    state = fields.Selection(
        selection=[
            ('nuova', 'Nuova'),
            ('approvata', 'Approvata'),
            ('rifiutata', 'Rifiutata'),
        ],
        string="Stato",
        default='nuova',
        tracking=True,
        required=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Socio creato",
        readonly=True,
        copy=False,
    )
    motivo_rifiuto = fields.Text(string="Motivo del rifiuto")

    @api.depends('nome', 'cognome')
    def _compute_name(self):
        for r in self:
            nome = (r.nome or '').strip()
            cognome = (r.cognome or '').strip()
            r.name = _("Richiesta - %s %s") % (nome, cognome) if (nome or cognome) \
                else _("Richiesta")

    def action_approva(self):
        Sequence = self.env['ir.sequence']
        for r in self:
            if r.state != 'nuova':
                raise UserError(_(
                    "Solo le richieste in stato 'Nuova' possono essere approvate."
                ))
            partner_vals = {
                'name': ("%s %s" % (r.nome or '', r.cognome or '')).strip(),
                'company_type': 'person',
                'email': r.email,
                'phone': r.telefono,
                'street': r.indirizzo,
                'zip': r.cap,
                'city': r.citta,
                'is_socio': True,
                'categoria_socio': r.categoria_richiesta or 'volontario',
                'stato_socio': 'attivo',
                'data_iscrizione': fields.Date.context_today(r),
                'comment': self._build_comment(r),
            }
            partner = self.env['res.partner'].create(partner_vals)
            partner.numero_socio = Sequence.next_by_code('crocevia.numero.socio')
            r.write({
                'state': 'approvata',
                'partner_id': partner.id,
            })
            r.message_post(body=_(
                "Richiesta approvata. Socio creato: <b>%s</b> (n. %s)."
            ) % (partner.display_name, partner.numero_socio))

    @staticmethod
    def _build_comment(r):
        """Allega al partner i dati che non hanno un campo nativo dedicato
        (codice fiscale, data e luogo di nascita, provincia)."""
        parts = []
        if r.codice_fiscale:
            parts.append(_("Codice fiscale: %s") % r.codice_fiscale)
        if r.data_nascita:
            parts.append(_("Nato il %s") % r.data_nascita)
        if r.luogo_nascita:
            parts.append(_("Luogo di nascita: %s") % r.luogo_nascita)
        if r.provincia:
            parts.append(_("Provincia: %s") % r.provincia)
        return "\n".join(parts) or False

    def action_rifiuta(self):
        for r in self:
            if r.state != 'nuova':
                raise UserError(_(
                    "Solo le richieste in stato 'Nuova' possono essere rifiutate."
                ))
            r.state = 'rifiutata'
            r.message_post(body=_("Richiesta rifiutata."))

    def action_view_partner(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Nessun socio collegato a questa richiesta."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Socio"),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
