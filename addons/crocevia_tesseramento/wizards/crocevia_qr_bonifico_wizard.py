"""
Wizard transient che mostra un QR EPC per fare un bonifico SEPA
precompilato verso il conto dell'APS.

Si apre dal bottone "QR bonifico" sulla scheda socio. I default
pescano da `ir.config_parameter`:
- iban -> `crocevia_tesseramento.iban`
- intestatario -> `crocevia_tesseramento.iban_intestatario`
- importo -> `crocevia_tesseramento.importo_mensile`
- causale -> auto-generata dal partner e dal mese corrente

Modificare importo o causale ricalcola al volo il QR.
"""

from odoo import api, fields, models, _

from ..utils.epc_qr import costruisci_payload_epc, genera_qr_png_base64


class CroceviaQrBonificoWizard(models.TransientModel):
    _name = 'crocevia.qr.bonifico.wizard'
    _description = "QR EPC per bonifico SEPA"

    partner_id = fields.Many2one(
        'res.partner',
        string="Socio",
        required=True,
    )
    iban = fields.Char(string="IBAN beneficiario")
    intestatario = fields.Char(string="Intestatario", default="Crocevia dei Mondi APS")
    importo = fields.Float(string="Importo (EUR)", required=True, default=10.0)
    causale = fields.Char(string="Causale", required=True)
    qr_image = fields.Binary(
        string="QR Code",
        compute='_compute_qr',
        readonly=True,
    )
    payload_testo = fields.Text(
        string="Payload EPC (debug)",
        compute='_compute_qr',
        readonly=True,
    )
    iban_mancante = fields.Boolean(
        compute='_compute_iban_mancante',
        store=False,
    )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        IcP = self.env['ir.config_parameter'].sudo()
        defaults['iban'] = IcP.get_param('crocevia_tesseramento.iban', '')
        defaults['intestatario'] = IcP.get_param(
            'crocevia_tesseramento.iban_intestatario', 'Crocevia dei Mondi APS')
        try:
            defaults['importo'] = float(IcP.get_param(
                'crocevia_tesseramento.importo_mensile', '10.0'))
        except (TypeError, ValueError):
            defaults['importo'] = 10.0

        # Pre-compila la causale con il prossimo mese del socio.
        partner_id = self.env.context.get('default_partner_id') or defaults.get('partner_id')
        if partner_id and 'causale' in fields_list and not defaults.get('causale'):
            partner = self.env['res.partner'].browse(partner_id)
            mese = fields.Date.context_today(self).strftime('%Y-%m')
            socio = ("Socio n.%s" % partner.numero_socio) if partner.numero_socio else partner.name
            defaults['causale'] = "Contributo %s - %s" % (mese, socio)
        return defaults

    @api.depends('iban')
    def _compute_iban_mancante(self):
        for w in self:
            w.iban_mancante = not (w.iban or '').strip()

    @api.depends('iban', 'intestatario', 'importo', 'causale')
    def _compute_qr(self):
        for w in self:
            if not (w.iban or '').strip():
                w.qr_image = False
                w.payload_testo = False
                continue
            payload = costruisci_payload_epc(
                beneficiario=w.intestatario,
                iban=w.iban,
                importo=w.importo,
                causale=w.causale,
            )
            w.payload_testo = payload
            w.qr_image = genera_qr_png_base64(payload)
