"""
Report PDF QWeb della ricevuta non fiscale.

Il template QWeb usa `web.external_layout` standard di Odoo per intestare
con logo e dati `res.company`. Sotto, la tabella della ricevuta e in
calce un QR EPC per facilitare il prossimo bonifico (se l'IBAN
dell'APS e' configurato nei parametri di sistema).
"""

from odoo import api, fields, models

from ..utils.epc_qr import costruisci_payload_epc, genera_qr_png_base64


class ReportCroceviaRicevuta(models.AbstractModel):
    _name = 'report.crocevia_tesseramento.report_crocevia_ricevuta_document'
    _description = "Report Ricevuta Crocevia"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['crocevia.ricevuta'].browse(docids)
        IcP = self.env['ir.config_parameter'].sudo()
        iban = (IcP.get_param('crocevia_tesseramento.iban', '') or '').strip()
        intestatario = IcP.get_param(
            'crocevia_tesseramento.iban_intestatario',
            'Crocevia dei Mondi APS',
        )
        try:
            importo_mensile = float(IcP.get_param(
                'crocevia_tesseramento.importo_mensile', '10.0'))
        except (TypeError, ValueError):
            importo_mensile = 10.0

        qr_per_doc = {}
        if iban:
            for doc in docs:
                mese = fields.Date.context_today(self).strftime('%Y-%m')
                socio = ("Socio n.%s" % doc.partner_id.numero_socio
                         ) if doc.partner_id.numero_socio else doc.partner_id.name
                causale = "Contributo %s - %s" % (mese, socio or '')
                payload = costruisci_payload_epc(
                    beneficiario=intestatario,
                    iban=iban,
                    importo=importo_mensile,
                    causale=causale,
                )
                qr_per_doc[doc.id] = genera_qr_png_base64(payload)

        return {
            'doc_ids': docids,
            'doc_model': 'crocevia.ricevuta',
            'docs': docs,
            'qr_per_doc': qr_per_doc,
            'iban_aps': iban,
        }
