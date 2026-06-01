"""
Log degli annullamenti del registro volontari.

Modello immutabile: una volta creato il record, niente write/unlink.
Non e' transient (TransientModel) - vogliamo la persistenza per
audit + ricostruzione storica.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CroceviaRegistroIscrizioneAnnullamento(models.Model):
    _name = 'crocevia.registro.iscrizione.annullamento'
    _description = "Annullamento di un'iscrizione al registro volontari"
    _order = 'data_annullamento desc, id desc'

    iscrizione_id = fields.Many2one(
        'crocevia.registro.iscrizione',
        string="Iscrizione annullata",
        required=True,
        ondelete='restrict',
        index=True,
    )
    motivazione = fields.Text(
        string="Motivazione",
        required=True,
        help="Descrizione del motivo dell'annullamento "
             "(minimo 20 caratteri).",
    )
    data_annullamento = fields.Datetime(
        string="Data annullamento",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    responsabile_id = fields.Many2one(
        'res.users',
        string="Responsabile",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )

    @api.depends('iscrizione_id', 'data_annullamento')
    def _compute_display_name(self):
        for r in self:
            isc = r.iscrizione_id.display_name or '?'
            data = r.data_annullamento and r.data_annullamento.strftime('%d/%m/%Y') or ''
            r.display_name = "Annullamento %s del %s" % (isc, data)

    def write(self, vals):
        # Log immutabile: solo creazione, nessuna modifica successiva.
        raise UserError(_(
            "I log di annullamento sono immutabili per audit. "
            "Per correggere, creare un nuovo record di annullamento."
        ))

    def unlink(self):
        raise UserError(_(
            "I log di annullamento non possono essere cancellati."
        ))
