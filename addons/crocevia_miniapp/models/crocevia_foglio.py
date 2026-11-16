"""Elenco dell'inventario per il foglio Google della biblioteca.

Il foglio e' solo una copia in lettura: uno script Apps Script chiama
`elenco` ogni tanto e riscrive una scheda. Si scrive solo in Odoo.

Chi chiama e' l'utente tecnico "Foglio inventario", un utente portale:
la sua chiave sta nelle proprieta' dello script, che chiunque possa
modificare il foglio puo' leggere. Per questo l'utente non ha accesso a
nessun modello e passa solo da qui, che restituisce le colonne del foglio
e niente altro. In particolare non chi ha in prestito un bene: solo se e'
in prestito e fino a quando.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

UTENTE = 'crocevia_miniapp.user_foglio'

STATI = {
    'disponibile': "Disponibile",
    'in_prestito': "In prestito",
    'mancante': "Mancante",
}

INTESTAZIONE = [
    "Sede", "Titolo", "Autore", "Editore", "Anno", "Genere", "ISBN",
    "Codice", "Stato", "Rientro previsto", "ID Odoo",
]


class CroceviaFoglio(models.AbstractModel):
    _name = 'crocevia.foglio'
    _description = "Elenco dell'inventario per il foglio Google"

    @api.model
    def elenco(self, sede=False, categoria='libro'):
        """Righe per il foglio, intestazione compresa.

        `sede`: nome della citta' (es. "Barletta"); vuoto = tutte le sedi.
        `categoria`: come in crocevia.bene; vuoto = tutte.
        """
        utente = self.env.ref(UTENTE, raise_if_not_found=False)
        if not (self.env.su or (utente and self.env.user == utente)):
            raise AccessError(_("Questa API è riservata al foglio dell'inventario."))

        dominio = []
        if categoria:
            dominio.append(('categoria', '=', categoria))
        if sede:
            dominio.append(('sede_id.citta', '=ilike', sede.strip()))
        beni = self.env['crocevia.bene'].sudo().search(
            dominio, order='sede_id, name, autore, id')

        righe = [INTESTAZIONE]
        for b in beni:
            rientro = b.prestito_corrente_id.data_restituzione_prevista
            righe.append([
                b.sede_id.citta or '',
                b.name or '',
                b.autore or '',
                b.editore or '',
                b.anno_pubblicazione or '',
                ', '.join(b.genere_ids.mapped('name')),
                b.isbn or '',
                b.codice_interno or '',
                STATI.get(b.stato_bene, b.stato_bene or ''),
                fields.Date.to_string(rientro) if rientro and b.in_prestito else '',
                b.id,
            ])
        return righe
