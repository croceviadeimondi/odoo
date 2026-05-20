"""
Wizard transient per registrare ricevute con flusso veloce.

Tre wizard, uno per ciascun tipo che richiede input variabili (importo
o mese):
- `crocevia.ricevuta.mensilita.wizard`  -> sceglie mese e conferma 10 EUR
- `crocevia.ricevuta.evento.wizard`     -> importo (default 3 EUR) e
                                           descrizione evento
- `crocevia.ricevuta.quota.wizard`      -> sceglie mese (la quota copre
                                           la prima mensilita')

L'obolo NON ha wizard: 2 EUR fissi, partono dalla scheda socio con un
click sul bottone "Obolo +2".

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
# Quota annuale (copre anche la prima mensilità)
# ---------------------------------------------------------------------

class CroceviaRicevutaQuotaWizard(models.TransientModel):
    _name = 'crocevia.ricevuta.quota.wizard'
    _description = "Registra quota associativa annuale"
    _inherit = 'crocevia.ricevuta.wizard.base'

    mese_riferimento = fields.Char(
        string="Mese coperto",
        required=True,
        size=7,
        default=lambda self: fields.Date.context_today(self).strftime('%Y-%m'),
        help="La quota annuale copre la prima mensilita': indica qui il "
             "mese a partire dal quale il socio risulta in regola "
             "(formato YYYY-MM).",
    )
    importo = fields.Monetary(
        string="Importo",
        required=True,
        default=lambda self: self._param(
            self.env, 'crocevia_tesseramento.importo_quota_annuale', '10.0'),
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
            'tipo': 'quota_annuale',
            'mese_riferimento': self.mese_riferimento,
            'importo': self.importo,
            'metodo': self.metodo,
            'riferimento': self.riferimento,
            'note': self.note,
        })
        return self._apri_ricevuta(r)


# ---------------------------------------------------------------------
# Contributo evento (importo libero, range 3-5 EUR)
# ---------------------------------------------------------------------

class CroceviaRicevutaEventoWizard(models.TransientModel):
    _name = 'crocevia.ricevuta.evento.wizard'
    _description = "Registra contributo evento"
    _inherit = 'crocevia.ricevuta.wizard.base'

    importo = fields.Monetary(
        string="Importo",
        required=True,
        default=lambda self: self._param(
            self.env, 'crocevia_tesseramento.importo_evento_default', '3.0'),
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    descrizione_evento = fields.Char(
        string="Nome evento",
        help="Es. 'Festival Crocevia 2026', 'Torneo Magic novembre'. "
             "Viene salvato nelle note della ricevuta per riferimento.",
    )

    def action_conferma(self):
        self.ensure_one()
        note_combinate = self.note or ''
        if self.descrizione_evento:
            riga_evento = _("Evento: %s") % self.descrizione_evento
            note_combinate = (riga_evento + "\n" + note_combinate
                              if note_combinate else riga_evento)
        r = self.env['crocevia.ricevuta'].create({
            'partner_id': self.partner_id.id,
            'data': self.data,
            'tipo': 'contributo_evento',
            'importo': self.importo,
            'metodo': self.metodo,
            'riferimento': self.riferimento,
            'note': note_combinate or False,
        })
        return self._apri_ricevuta(r)
