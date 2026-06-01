from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


CATEGORIE_CON_EDITORIALE = ('libro', 'manuale', 'gioco_di_ruolo')


class CroceviaBeneWizard(models.TransientModel):
    """Wizard a 3 step per inserire un singolo bene nell'inventario.

    Pensato per gli inserimenti uno alla volta (alternativa al form
    classico e all'import csv di massa). Guida l'utente attraverso
    identificazione, dettagli editoriali (se la categoria lo richiede)
    e dati di chiusura (codice interno, valore, note).
    """

    _name = 'crocevia.bene.wizard'
    _description = "Inserimento guidato di un bene"

    state = fields.Selection(
        selection=[
            ('identificazione', 'Identificazione'),
            ('dettagli', 'Dettagli editoriali'),
            ('conclusione', 'Riepilogo e salvataggio'),
        ],
        default='identificazione',
        required=True,
    )

    # ---- Step 1: identificazione ----
    name = fields.Char(string="Titolo")
    categoria = fields.Selection(
        selection=[
            ('gioco_da_tavolo', 'Gioco da tavolo'),
            ('gioco_di_ruolo', 'Gioco di ruolo'),
            ('manuale', 'Manuale'),
            ('libro', 'Libro'),
            ('altro', 'Altro'),
        ],
        string="Categoria",
        default='libro',
    )
    sede_id = fields.Many2one(
        'crocevia.sede',
        string="Sede",
    )

    # ---- Step 2: dettagli editoriali ----
    autore = fields.Char(string="Autore")
    editore = fields.Char(string="Editore")
    anno_pubblicazione = fields.Integer(string="Anno pubblicazione")
    isbn = fields.Char(string="ISBN")

    # ---- Step 3: conclusione ----
    codice_interno = fields.Char(string="Codice interno")
    valore_stimato = fields.Monetary(string="Valore stimato")
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    note = fields.Text(string="Note")

    # Risultato (popolato solo dopo l'azione "Salva")
    bene_id = fields.Many2one('crocevia.bene', readonly=True)

    # ----------------- navigazione step -----------------

    def action_avanti(self):
        self.ensure_one()
        if self.state == 'identificazione':
            self._valida_identificazione()
            self.state = 'dettagli'
        elif self.state == 'dettagli':
            self.state = 'conclusione'
        return self._reopen()

    def action_indietro(self):
        self.ensure_one()
        if self.state == 'conclusione':
            self.state = 'dettagli'
        elif self.state == 'dettagli':
            self.state = 'identificazione'
        return self._reopen()

    # ----------------- salvataggio -----------------

    def _crea_bene(self):
        self.ensure_one()
        self._valida_identificazione()
        return self.env['crocevia.bene'].create({
            'name': self.name,
            'categoria': self.categoria,
            'sede_id': self.sede_id.id,
            'autore': self.autore or False,
            'editore': self.editore or False,
            'anno_pubblicazione': self.anno_pubblicazione or 0,
            'isbn': self.isbn or False,
            'codice_interno': self.codice_interno or False,
            'valore_stimato': self.valore_stimato or 0.0,
            'currency_id': self.currency_id.id,
            'note': self.note or False,
        })

    def action_salva(self):
        """Crea il bene e apre la sua scheda."""
        self.ensure_one()
        bene = self._crea_bene()
        self.bene_id = bene.id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Bene creato"),
            'res_model': 'crocevia.bene',
            'res_id': bene.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_salva_e_nuovo(self):
        """Crea il bene e riapre un wizard pulito per inserirne un altro."""
        self.ensure_one()
        bene = self._crea_bene()
        # Pre-popoliamo la sede (di solito si caricano piu' beni della
        # stessa sede in sequenza) per ridurre attriti.
        return {
            'type': 'ir.actions.act_window',
            'name': _("Aggiungi un altro bene"),
            'res_model': 'crocevia.bene.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sede_id': bene.sede_id.id,
                'default_categoria': bene.categoria,
            },
        }

    # ----------------- helpers -----------------

    def _valida_identificazione(self):
        if not (self.name and self.name.strip()):
            raise ValidationError(_("Inserisci il titolo del bene."))
        if not self.sede_id:
            raise ValidationError(_("Seleziona la sede dove si trova il bene."))
        if not self.categoria:
            raise ValidationError(_("Seleziona una categoria."))

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crocevia.bene.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.onchange('categoria')
    def _onchange_categoria(self):
        # Se la categoria non ha dettagli editoriali, puliamo i campi
        # cosi' non restano valori "fantasma" dello step precedente.
        if self.categoria not in CATEGORIE_CON_EDITORIALE:
            self.isbn = False
