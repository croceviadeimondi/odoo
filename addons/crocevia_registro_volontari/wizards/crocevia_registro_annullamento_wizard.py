"""
Wizard transient per annullare un'iscrizione del registro volontari.
Richiede motivazione di almeno 20 caratteri (SPEC 4.3).

L'annullamento NON cancella il record (write-once). Crea un log
permanente in `crocevia.registro.iscrizione.annullamento` e setta il
campo `annullamento_id` sul record originale (e' l'unica eccezione
all'inalterabilita' del modello iscrizione).
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CroceviaRegistroAnnullamentoWizard(models.TransientModel):
    _name = 'crocevia.registro.annullamento.wizard'
    _description = "Annulla iscrizione registro volontari"

    iscrizione_id = fields.Many2one(
        'crocevia.registro.iscrizione',
        string="Iscrizione da annullare",
        required=True,
    )
    motivazione = fields.Text(
        string="Motivazione",
        required=True,
        help="Spiega in modo chiaro il motivo dell'annullamento. "
             "Minimo 20 caratteri.",
    )

    @api.constrains('motivazione')
    def _check_motivazione(self):
        for w in self:
            if not w.motivazione or len(w.motivazione.strip()) < 20:
                raise ValidationError(_(
                    "La motivazione deve essere lunga almeno 20 caratteri."
                ))

    def action_conferma(self):
        self.ensure_one()
        if self.iscrizione_id.stato == 'annullato':
            raise ValidationError(_(
                "L'iscrizione e' gia' annullata."
            ))
        # Crea log immutabile.
        log = self.env['crocevia.registro.iscrizione.annullamento'].create({
            'iscrizione_id': self.iscrizione_id.id,
            'motivazione': self.motivazione.strip(),
        })
        # Aggiorna il record originale: e' l'unica eccezione al
        # write-once (vedi `_CAMPI_WRITE_ONCE` dell'iscrizione: questi
        # 2 campi NON ci sono dentro, quindi write passa).
        self.iscrizione_id.write({
            'annullamento_id': log.id,
            'motivo_annullamento': self.motivazione.strip(),
        })
        self.iscrizione_id.message_post(body=_(
            "Iscrizione annullata da %s. Motivazione: %s"
        ) % (self.env.user.name, self.motivazione.strip()))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Iscrizione annullata"),
            'res_model': 'crocevia.registro.iscrizione',
            'res_id': self.iscrizione_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
