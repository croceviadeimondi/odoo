"""
Modello `crocevia.ricevuta`: ricevute non fiscali rilasciate ai soci.

Per un'APS le entrate verso i soci NON sono fatture IVA (art. 4 DPR
633/72 e art. 85 CTS: quote associative e contributi istituzionali sono
fuori campo IVA / de-commercializzati). Si rilasciano ricevute non
fiscali numerate progressivamente, da consegnare al socio.

Tipi di ricevuta supportati:
- `tesseramento`         (10 EUR di default, copre la prima mensilita'
                          del mese di rinnovo)
- `contributo_mensile`   (10 EUR di default)
- `obolo_giornaliero`    (2 EUR di default)
- `contributo_evento`    (3 EUR di default, range tipico 3-5 EUR)
- `donazione`            (importo libero)
- `altro`                (importo libero)

Importi default modificabili da Impostazioni > Tecnico > Parametri di
sistema con chiavi `crocevia_tesseramento.importo_*`.
"""

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


TIPO_RICEVUTA_SELECTION = [
    ('tesseramento', 'Tesseramento (quota annuale)'),
    ('contributo_mensile', 'Contributo mensile'),
    ('obolo_giornaliero', 'Obolo giornaliero'),
    ('contributo_evento', 'Contributo evento'),
    ('donazione', 'Donazione'),
    ('altro', 'Altro'),
]

METODO_PAGAMENTO_SELECTION = [
    ('contanti', 'Contanti'),
    ('paypal', 'PayPal'),
    ('satispay', 'Satispay'),
    ('bonifico', 'Bonifico bancario'),
    ('altro', 'Altro'),
]

# Tipi che richiedono `mese_riferimento` (per il calcolo di chi e' in
# regola con la mensilita' di un certo mese).
TIPI_CON_MESE = ('contributo_mensile', 'tesseramento')

# Formato accettato per `mese_riferimento`: YYYY-MM (regex permissivo).
MESE_REGEX = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

NOME_PLACEHOLDER = "Nuovo"


class CroceviaRicevuta(models.Model):
    _name = 'crocevia.ricevuta'
    _description = "Ricevuta non fiscale"
    _inherit = ['mail.thread']
    _order = 'data desc, id desc'

    numero = fields.Char(
        string="Numero",
        readonly=True,
        copy=False,
        default=lambda self: NOME_PLACEHOLDER,
        tracking=True,
        help="Assegnato automaticamente dalla sequenza `crocevia.ricevuta` "
             "alla creazione (formato RIC/YYYY/NNNN).",
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Socio",
        required=True,
        tracking=True,
        index=True,
        domain="[('is_socio', '=', True)]",
    )
    data = fields.Date(
        string="Data",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    tipo = fields.Selection(
        selection=TIPO_RICEVUTA_SELECTION,
        string="Tipo",
        required=True,
        default='contributo_mensile',
        tracking=True,
    )
    mese_riferimento = fields.Char(
        string="Mese di riferimento",
        size=7,
        help="Formato YYYY-MM. Richiesto per tipi 'tesseramento' e "
             "'contributo_mensile' (il tesseramento annuale copre la "
             "prima mensilita' del mese qui indicato).",
    )
    importo = fields.Monetary(
        string="Importo",
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    metodo = fields.Selection(
        selection=METODO_PAGAMENTO_SELECTION,
        string="Metodo di pagamento",
        required=True,
        default='contanti',
        tracking=True,
    )
    riferimento = fields.Char(
        string="Riferimento",
        help="ID transazione PayPal/Satispay, numero scontrino, CRO "
             "bonifico, oppure altra annotazione per ritrovare il "
             "movimento sul conto.",
    )
    note = fields.Text(string="Note")

    # Link opzionale a scrittura contabile.
    account_move_id = fields.Many2one(
        'account.move',
        string="Scrittura contabile",
        readonly=True,
        copy=False,
    )

    # ----------------- create / numero -----------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('numero') or vals.get('numero') == NOME_PLACEHOLDER:
                seq = self.env['ir.sequence'].next_by_code('crocevia.ricevuta')
                vals['numero'] = seq or NOME_PLACEHOLDER
        return super().create(vals_list)

    # ----------------- vincoli -----------------

    @api.constrains('tipo', 'mese_riferimento')
    def _check_mese_riferimento(self):
        for r in self:
            if r.tipo in TIPI_CON_MESE:
                if not r.mese_riferimento:
                    raise ValidationError(_(
                        "Il mese di riferimento e' obbligatorio per le "
                        "ricevute di tipo Tesseramento o Contributo "
                        "mensile."
                    ))
                if not MESE_REGEX.match(r.mese_riferimento):
                    raise ValidationError(_(
                        "Il mese di riferimento '%s' non e' in formato "
                        "YYYY-MM (es. 2026-05)."
                    ) % r.mese_riferimento)

    @api.constrains('importo')
    def _check_importo_positivo(self):
        for r in self:
            if r.importo <= 0:
                raise ValidationError(_(
                    "L'importo della ricevuta deve essere maggiore di zero."
                ))

    # ----------------- onchange ergonomia -----------------

    @api.onchange('tipo')
    def _onchange_tipo(self):
        """Pre-popola importo e mese in base al tipo selezionato."""
        if not self.tipo:
            return
        IcP = self.env['ir.config_parameter'].sudo()
        defaults_per_tipo = {
            'tesseramento': 'crocevia_tesseramento.importo_tesseramento',
            'contributo_mensile': 'crocevia_tesseramento.importo_mensile',
            'obolo_giornaliero': 'crocevia_tesseramento.importo_obolo',
            'contributo_evento': 'crocevia_tesseramento.importo_evento_default',
        }
        if self.tipo in defaults_per_tipo:
            try:
                self.importo = float(IcP.get_param(
                    defaults_per_tipo[self.tipo], '0.0'))
            except (TypeError, ValueError):
                self.importo = 0.0
        if self.tipo in TIPI_CON_MESE and not self.mese_riferimento:
            today = fields.Date.context_today(self)
            self.mese_riferimento = today.strftime('%Y-%m')
        if self.tipo not in TIPI_CON_MESE:
            self.mese_riferimento = False

    # ----------------- display name -----------------

    @api.depends('numero', 'partner_id', 'tipo', 'importo')
    def _compute_display_name(self):
        tipo_dict = dict(TIPO_RICEVUTA_SELECTION)
        for r in self:
            partner = r.partner_id.display_name or '?'
            tipo_label = tipo_dict.get(r.tipo, r.tipo or '')
            num = r.numero if r.numero and r.numero != NOME_PLACEHOLDER else '(nuova)'
            r.display_name = "%s - %s - %s" % (num, partner, tipo_label)
