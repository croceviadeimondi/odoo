"""
Report PDF QWeb dello snapshot del registro volontari.

Il PDF deve essere deterministico: lo stesso snapshot deve produrre
lo stesso hash. Per ottenerlo:
- Niente timestamp variabili nei metadati (passiamo `data_snapshot`
  dal contesto della vidimazione invece di `now()`)
- ID PDF normalizzato post-rendering con `qpdf --deterministic-id`
  (vedi `crocevia.registro.vidimazione._normalizza_pdf`)
"""

from odoo import api, fields, models


class ReportRegistroVolontari(models.AbstractModel):
    _name = 'report.crocevia_registro_volontari.report_volontari_doc'
    _description = "Report snapshot registro volontari"

    @api.model
    def _get_report_values(self, docids, data=None):
        Vid = self.env['crocevia.registro.vidimazione']
        Isc = self.env['crocevia.registro.iscrizione']
        Ann = self.env['crocevia.registro.iscrizione.annullamento']

        docs = Vid.browse(docids)

        # Tutti gli iscritti (anche cessati / annullati: il registro
        # legale li riporta tutti, con il loro stato).
        iscrizioni_abituali = Isc.search(
            [('tipo', '=', 'abituale')],
            order='numero_iscrizione asc')
        iscrizioni_occasionali = Isc.search(
            [('tipo', '=', 'occasionale')],
            order='numero_iscrizione asc')
        annullamenti = Ann.search([], order='data_annullamento desc')

        company = self.env.company
        # CF dell'APS: leggiamo da res.company.vat (Odoo nativo). Per
        # APS senza P.IVA il CF si mette li' come da prassi italiana.
        cf_aps = company.vat or ''

        # Riepilogo numerico
        totali = {
            'iscritti': Isc.search_count([('stato', '=', 'iscritto')]),
            'cessati': Isc.search_count([('stato', '=', 'cessato')]),
            'annullati': Isc.search_count([('stato', '=', 'annullato')]),
        }

        return {
            'doc_ids': docids,
            'doc_model': 'crocevia.registro.vidimazione',
            'docs': docs,
            'iscrizioni_abituali': iscrizioni_abituali,
            'iscrizioni_occasionali': iscrizioni_occasionali,
            'annullamenti': annullamenti,
            'company': company,
            'cf_aps': cf_aps,
            'totali': totali,
            'data_snapshot': self.env.context.get(
                'data_snapshot') or fields.Datetime.now(),
        }
