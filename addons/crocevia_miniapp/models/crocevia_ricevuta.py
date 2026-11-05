from odoo import fields, models


class CroceviaRicevuta(models.Model):
    _inherit = 'crocevia.ricevuta'

    # Una ricevuta segnata per sbaglio dalla miniapp non si cancella: il
    # numero e' gia' uscito dalla sequenza e deve restare. Si archivia, e
    # da quel momento non conta piu' per mensilita', spese e rinnovi.
    active = fields.Boolean(default=True, tracking=True)
    metodo = fields.Selection(selection_add=[('stripe', 'Carta')],
                              ondelete={'stripe': 'set default'})
    evento = fields.Char(
        string="Evento",
        help="Per un contributo evento: il nome dell'evento, come l'ha "
             "scelto chi l'ha segnato dalla miniapp.")
    annullata_da = fields.Char(string="Annullata da", readonly=True, copy=False)
    annullata_il = fields.Datetime(string="Annullata il", readonly=True, copy=False)
