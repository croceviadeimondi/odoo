"""
Wizard per cessare un'iscrizione (volontario che termina l'attivita').
Imposta `data_fine_attivita` (l'unico campo modificabile post-creazione,
e solo da NULL a un valore - poi diventa write-once a sua volta).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CroceviaRegistroCessazioneWizard(models.TransientModel):
    _name = 'crocevia.registro.cessazione.wizard'
    _description = "Cessa iscrizione registro volontari"

    iscrizione_id = fields.Many2one(
        'crocevia.registro.iscrizione',
        string="Iscrizione",
        required=True,
    )
    data_fine = fields.Date(
        string="Data fine attivita'",
        required=True,
        default=fields.Date.context_today,
    )
    note = fields.Text(string="Note (opzionali)")

    @api.constrains('data_fine', 'iscrizione_id')
    def _check_data_fine(self):
        for w in self:
            if not w.iscrizione_id:
                continue
            if w.data_fine < w.iscrizione_id.data_inizio_attivita:
                raise ValidationError(_(
                    "La data di fine attivita' non puo' essere antecedente "
                    "alla data di inizio (%s)."
                ) % w.iscrizione_id.data_inizio_attivita.strftime('%d/%m/%Y'))

    def action_conferma(self):
        self.ensure_one()
        if self.iscrizione_id.stato != 'iscritto':
            raise UserError(_(
                "Si possono cessare solo iscrizioni con stato 'Iscritto'. "
                "Stato attuale: %s."
            ) % dict(self.iscrizione_id._fields['stato'].selection).get(
                self.iscrizione_id.stato))
        self.iscrizione_id.data_fine_attivita = self.data_fine
        msg = _("Cessazione registrata, data fine: %s.") % self.data_fine.strftime('%d/%m/%Y')
        if self.note:
            msg += "\n" + _("Note: ") + self.note
        self.iscrizione_id.message_post(body=msg)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crocevia.registro.iscrizione',
            'res_id': self.iscrizione_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
