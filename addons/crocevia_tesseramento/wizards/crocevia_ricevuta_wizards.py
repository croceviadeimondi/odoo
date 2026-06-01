"""
Wizard transient per registrare ricevute con flusso veloce.

Due wizard, uno per ciascun tipo registrato dalla scheda socio:
- `crocevia.ricevuta.mensilita.wizard`  -> sceglie mese e importo (10 EUR)
- `crocevia.ricevuta.obolo.wizard`      -> importo (default 2 EUR)

Il tesseramento non ha quick-action: e' implicito nell'iscrizione al
libro soci e la prima mensilita' lo copre gia'. Il contributo evento
resta un `tipo` di ricevuta, ma si crea dalla scheda ricevuta a mano.

Tutti i wizard hanno `partner_id` precompilato dal contesto, e creano
un record `crocevia.ricevuta` alla conferma.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


METODO_PAGAMENTO_SELECTION = [
    ('contanti', 'Contanti'),
    ('paypal', 'PayPal'),
    ('satispay', 'Satispay'),
    ('bonifico', 'Bonifico bancario'),
    ('altro', 'Altro'),
]


class _BaseRicevutaWizard(models.AbstractModel):
    """Base condivisa: campi comuni + helper di creazione ricevuta."""

    _name = 'crocevia.ricevuta.wizard.base'
    _description = "Base wizard ricevuta (astratto)"

    partner_id = fields.Many2one(
        'res.partner',
        string="Socio",
        required=True,
        domain="[('is_socio', '=', True)]",
    )
    data = fields.Date(
        string="Data",
        required=True,
        default=fields.Date.context_today,
    )
    metodo = fields.Selection(
        selection=METODO_PAGAMENTO_SELECTION,
        string="Metodo di pagamento",
        required=True,
        default='contanti',
    )
    riferimento = fields.Char(
        string="Riferimento",
        help="ID transazione PayPal/Satispay, n. scontrino, CRO bonifico.",
    )
    note = fields.Text(string="Note")

    def _apri_ricevuta(self, ricevuta):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ricevuta creata"),
            'res_model': 'crocevia.ricevuta',
            'res_id': ricevuta.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @staticmethod
    def _param(env, key, default):
        try:
            return float(env['ir.config_parameter'].sudo()
                         .get_param(key, default))
        except (TypeError, ValueError):
            return float(default)


# ---------------------------------------------------------------------
# Mensilità
# ---------------------------------------------------------------------

class CroceviaRicevutaMensilitaWizard(models.TransientModel):
    _name = 'crocevia.ricevuta.mensilita.wizard'
    _description = "Registra contributo mensile"
    _inherit = 'crocevia.ricevuta.wizard.base'

    mese_riferimento = fields.Char(
        string="Mese di riferimento",
        required=True,
        size=7,
        default=lambda self: fields.Date.context_today(self).strftime('%Y-%m'),
        help="Formato YYYY-MM (es. 2026-05).",
    )
    importo = fields.Monetary(
        string="Importo",
        required=True,
        default=lambda self: self._param(
            self.env, 'crocevia_tesseramento.importo_mensile', '10.0'),
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    def action_conferma(self):
        self.ensure_one()
        r = self.env['crocevia.ricevuta'].create({
            'partner_id': self.partner_id.id,
            'data': self.data,
            'tipo': 'contributo_mensile',
            'mese_riferimento': self.mese_riferimento,
            'importo': self.importo,
            'metodo': self.metodo,
            'riferimento': self.riferimento,
            'note': self.note,
        })
        return self._apri_ricevuta(r)


# ---------------------------------------------------------------------
# Obolo giornaliero (importo modificabile, default 2 EUR)
# ---------------------------------------------------------------------

class CroceviaRicevutaOboloWizard(models.TransientModel):
    _name = 'crocevia.ricevuta.obolo.wizard'
    _description = "Registra obolo"
    _inherit = 'crocevia.ricevuta.wizard.base'

    importo = fields.Monetary(
        string="Importo",
        required=True,
        default=lambda self: self._param(
            self.env, 'crocevia_tesseramento.importo_obolo', '2.0'),
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    def action_conferma(self):
        self.ensure_one()
        r = self.env['crocevia.ricevuta'].create({
            'partner_id': self.partner_id.id,
            'data': self.data,
            'tipo': 'obolo_giornaliero',
            'importo': self.importo,
            'metodo': self.metodo,
            'riferimento': self.riferimento,
            'note': self.note,
        })
        return self._apri_ricevuta(r)
