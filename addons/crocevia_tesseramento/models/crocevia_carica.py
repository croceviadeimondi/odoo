from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


RUOLO_SELECTION = [
    ('presidente', 'Presidente'),
    ('vicepresidente', 'Vicepresidente'),
    ('segretario', 'Segretario'),
    ('tesoriere', 'Tesoriere'),
]


class CroceviaCarica(models.Model):
    _name = 'crocevia.carica'
    _description = "Carica direttiva"
    _order = 'data_nomina desc, id desc'

    partner_id = fields.Many2one(
        'res.partner',
        string="Socio",
        required=True,
        ondelete='cascade',
        index=True,
        domain=[('is_socio', '=', True)],
    )
    ruolo = fields.Selection(
        selection=RUOLO_SELECTION,
        string="Ruolo",
        required=True,
    )
    data_nomina = fields.Date(string="Data nomina", required=True)
    data_scadenza = fields.Date(
        string="Data scadenza",
        help="Lascia vuoto se il mandato è in corso e senza termine fissato.",
    )
    is_attuale = fields.Boolean(
        string="In carica",
        compute='_compute_is_attuale',
        store=True,
    )
    note = fields.Text(
        string="Note",
        help="Es. estremi della delibera di nomina (assemblea / direttivo).",
    )

    @api.depends('data_nomina', 'data_scadenza')
    def _compute_is_attuale(self):
        today = fields.Date.context_today(self)
        for c in self:
            c.is_attuale = bool(
                c.data_nomina and c.data_nomina <= today
                and (not c.data_scadenza or c.data_scadenza >= today)
            )

    @api.constrains('ruolo', 'data_nomina', 'data_scadenza', 'partner_id')
    def _check_nessuna_sovrapposizione(self):
        # Una sola persona può ricoprire un dato ruolo nello stesso periodo.
        # Controlliamo la sovrapposizione di intervalli di mandato per ruolo.
        for c in self:
            if not c.data_nomina:
                continue
            scadenza = c.data_scadenza or fields.Date.from_string('9999-12-31')
            overlap = self.search([
                ('id', '!=', c.id),
                ('ruolo', '=', c.ruolo),
                ('data_nomina', '<=', scadenza),
                '|',
                ('data_scadenza', '=', False),
                ('data_scadenza', '>=', c.data_nomina),
            ], limit=1)
            if overlap:
                raise ValidationError(_(
                    "Esiste già una carica '%(ruolo)s' che si sovrappone a "
                    "questo periodo (intestata a %(partner)s, dal "
                    "%(da)s%(al)s). Imposta una data di scadenza coerente "
                    "prima di registrare la nuova carica."
                ) % {
                    'ruolo': dict(RUOLO_SELECTION)[c.ruolo],
                    'partner': overlap.partner_id.display_name,
                    'da': overlap.data_nomina,
                    'al': (" al %s" % overlap.data_scadenza)
                           if overlap.data_scadenza else " (in corso)",
                })

    @api.depends('ruolo', 'partner_id', 'data_nomina')
    def _compute_display_name(self):
        ruolo_dict = dict(RUOLO_SELECTION)
        for c in self:
            ruolo_label = ruolo_dict.get(c.ruolo, c.ruolo or '')
            partner_name = c.partner_id.display_name or '-'
            c.display_name = "%s - %s" % (ruolo_label, partner_name)
