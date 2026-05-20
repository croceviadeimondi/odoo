"""
Modello `crocevia.registro.iscrizione`: una riga del registro volontari.

Caratteristiche cruciali per la conformita' al DM 6 ottobre 2021 e
all'art. 2215-bis cc:

1. **Write-once**: i campi anagrafici e di iscrizione sono congelati
   alla creazione. L'override di `write()` blocca le modifiche,
   `unlink()` lancia sempre errore.
2. **Hash chain**: ogni record ha un `hash_record` SHA-256 calcolato sui
   campi anagrafici + `hash_precedente`, dove `hash_precedente` =
   `hash_record` del record con numero immediatamente precedente. Cosi'
   una manomissione SQL diretta rompe la catena e si rileva con
   l'azione "Verifica catena".
3. **Numerazione progressiva mai riusata**: anche se un'iscrizione
   viene annullata, il suo numero resta occupato.
"""

import hashlib
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


TIPO_VOLONTARIO_SELECTION = [
    ('abituale', 'Abituale (art. 17 c.1 CTS)'),
    ('occasionale', 'Occasionale (art. 17 c.2 CTS)'),
]

STATO_SELECTION = [
    ('iscritto', 'Iscritto'),
    ('cessato', 'Cessato'),
    ('annullato', 'Annullato'),
]

# Regex CF persona fisica italiano standard (16 caratteri alfanumerici).
# Non valida il check digit ma e' sufficiente per il filtro di input.
CF_REGEX = re.compile(r'^[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]$')

HASH_ZERO = '0' * 64


class CroceviaRegistroIscrizione(models.Model):
    _name = 'crocevia.registro.iscrizione'
    _description = "Iscrizione al registro volontari ETS"
    _inherit = ['mail.thread']
    _order = 'numero_iscrizione asc'

    # ============ campi WRITE-ONCE ============
    numero_iscrizione = fields.Integer(
        string="N. iscrizione",
        readonly=True,
        copy=False,
        index=True,
        help="Assegnato dalla sequenza `crocevia.registro.volontario` "
             "alla creazione. Mai riusato.",
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Anagrafica (res.partner)",
        required=True,
        tracking=True,
        help="Contatto Odoo da cui sono stati snapshottati i dati. "
             "Le modifiche successive al contatto NON aggiornano il "
             "registro (per legge).",
    )
    # Snapshot anagrafico al momento dell'iscrizione (write-once).
    nome = fields.Char(string="Nome", required=True, tracking=True)
    cognome = fields.Char(string="Cognome", required=True, tracking=True)
    codice_fiscale = fields.Char(
        string="Codice fiscale",
        size=16,
        required=True,
        index=True,
        tracking=True,
    )
    data_nascita = fields.Date(string="Data di nascita",
                               required=True, tracking=True)
    luogo_nascita = fields.Char(string="Luogo di nascita",
                                required=True, tracking=True)
    indirizzo_residenza = fields.Char(string="Indirizzo residenza",
                                      required=True, tracking=True)
    cap_residenza = fields.Char(string="CAP", size=5,
                                required=True, tracking=True)
    citta_residenza = fields.Char(string="Citta'", required=True, tracking=True)
    provincia_residenza = fields.Char(string="Provincia",
                                      size=2, required=True, tracking=True)
    tipo = fields.Selection(
        selection=TIPO_VOLONTARIO_SELECTION,
        string="Tipo volontario",
        required=True,
        default='abituale',
        tracking=True,
    )
    data_inizio_attivita = fields.Date(
        string="Data inizio attivita'",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    attivita_svolta = fields.Text(
        string="Attivita' svolta",
        required=True,
        tracking=True,
        help="Descrizione delle mansioni del volontario.",
    )
    consenso_privacy_data = fields.Datetime(
        string="Data consenso privacy",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help="Momento in cui il volontario ha sottoscritto l'informativa "
             "privacy (art. 13 GDPR).",
    )

    # ============ campi PARZIALMENTE MUTABILI ============
    # data_fine_attivita: ammessa modifica da NULL a una data (cessazione).
    # Una volta valorizzata diventa write-once a sua volta.
    data_fine_attivita = fields.Date(
        string="Data fine attivita'",
        tracking=True,
        help="Se il volontario cessa l'attivita'. Si imposta una sola "
             "volta tramite il wizard 'Cessa iscrizione'.",
    )

    # ============ hash chain ============
    hash_record = fields.Char(
        string="Hash record (SHA-256)",
        size=64,
        readonly=True,
        copy=False,
    )
    hash_precedente = fields.Char(
        string="Hash record precedente",
        size=64,
        readonly=True,
        copy=False,
    )

    # ============ annullamento ============
    annullamento_id = fields.Many2one(
        'crocevia.registro.iscrizione.annullamento',
        string="Annullamento",
        readonly=True,
        copy=False,
    )
    motivo_annullamento = fields.Text(
        string="Motivo annullamento",
        readonly=True,
        copy=False,
    )

    stato = fields.Selection(
        selection=STATO_SELECTION,
        string="Stato",
        compute='_compute_stato',
        store=True,
        index=True,
    )

    # ----------------- computed -----------------

    @api.depends('annullamento_id', 'data_fine_attivita')
    def _compute_stato(self):
        for r in self:
            if r.annullamento_id:
                r.stato = 'annullato'
            elif r.data_fine_attivita:
                r.stato = 'cessato'
            else:
                r.stato = 'iscritto'

    @api.depends('numero_iscrizione', 'cognome', 'nome')
    def _compute_display_name(self):
        for r in self:
            num = ("%06d " % r.numero_iscrizione) if r.numero_iscrizione else ''
            r.display_name = "%s%s %s" % (num, r.cognome or '', r.nome or '')

    # ----------------- vincoli SQL -----------------
    _sql_constraints = [
        ('numero_iscrizione_unique',
         'UNIQUE(numero_iscrizione)',
         "Numero di iscrizione duplicato nel registro."),
    ]

    @api.constrains('codice_fiscale', 'stato')
    def _check_codice_fiscale_unico_attivo(self):
        """Non possono esistere due iscrizioni con stato='iscritto' e
        stesso CF (un volontario non puo' avere 2 iscrizioni attive)."""
        for r in self:
            if r.stato == 'iscritto' and r.codice_fiscale:
                doppione = self.search([
                    ('id', '!=', r.id),
                    ('codice_fiscale', '=', r.codice_fiscale),
                    ('stato', '=', 'iscritto'),
                ], limit=1)
                if doppione:
                    raise ValidationError(_(
                        "Esiste gia' un'iscrizione attiva con il codice "
                        "fiscale %s (n. %s, %s). Cessare quella prima "
                        "di crearne una nuova."
                    ) % (r.codice_fiscale,
                         doppione.numero_iscrizione,
                         doppione.display_name))

    @api.constrains('codice_fiscale')
    def _check_formato_cf(self):
        for r in self:
            if r.codice_fiscale:
                cf = r.codice_fiscale.upper().strip()
                if not CF_REGEX.match(cf):
                    raise ValidationError(_(
                        "Codice fiscale '%s' non valido. Formato atteso: "
                        "16 caratteri RRRSSSAAMGGCCCC (es. RSSMRA80A01H501U)."
                    ) % r.codice_fiscale)

    # ----------------- create / hash chain -----------------

    @api.model_create_multi
    def create(self, vals_list):
        # Controllo che esista una vidimazione recente o che sia la prima
        # iscrizione in assoluto (art. 2215-bis cc, vedi sezione 5.6 SPEC).
        self._verifica_vidimazione_recente()

        records = self.env['crocevia.registro.iscrizione']
        Sequence = self.env['ir.sequence']
        for vals in vals_list:
            # Normalizza CF in maiuscolo prima di salvare.
            if vals.get('codice_fiscale'):
                vals['codice_fiscale'] = vals['codice_fiscale'].upper().strip()

            # Numero progressivo dalla sequenza dedicata.
            if not vals.get('numero_iscrizione'):
                next_n = Sequence.next_by_code('crocevia.registro.volontario')
                vals['numero_iscrizione'] = int(next_n) if next_n else 1

            # Hash precedente = hash del record con numero precedente
            # (se esiste). Per il primo record: hash_precedente = 0*64.
            prev = self.search([
                ('numero_iscrizione', '<', vals['numero_iscrizione']),
            ], order='numero_iscrizione desc', limit=1)
            vals['hash_precedente'] = prev.hash_record if prev else HASH_ZERO

            # Hash del record stesso. Calcoliamo dal payload dei vals
            # (non da self perche' il record non esiste ancora).
            vals['hash_record'] = self._calcola_hash_da_vals(vals)

            rec = super().create([vals])
            records |= rec
        return records

    @staticmethod
    def _campi_in_hash():
        """Campi inclusi nel calcolo dell'hash record, in ordine
        deterministico. Tenere allineato con `_calcola_hash_da_vals`."""
        return [
            'numero_iscrizione', 'nome', 'cognome', 'codice_fiscale',
            'data_nascita', 'luogo_nascita',
            'indirizzo_residenza', 'cap_residenza',
            'citta_residenza', 'provincia_residenza',
            'tipo', 'data_inizio_attivita', 'hash_precedente',
        ]

    @classmethod
    def _calcola_hash_da_vals(cls, vals):
        pezzi = []
        for k in cls._campi_in_hash():
            v = vals.get(k)
            if v is None or v is False:
                pezzi.append('')
            elif isinstance(v, (int, float)):
                pezzi.append(str(v))
            elif hasattr(v, 'isoformat'):
                pezzi.append(v.isoformat())
            else:
                pezzi.append(str(v))
        payload = '|'.join(pezzi).encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

    def _calcola_hash_da_self(self):
        self.ensure_one()
        vals = {k: self[k] for k in self._campi_in_hash() if k in self._fields}
        return self._calcola_hash_da_vals(vals)

    def action_verifica_catena(self):
        """Ricalcola tutti gli hash della catena e mostra il primo
        punto di rottura, se esiste. Read-only sul DB."""
        record_ordinati = self.search([], order='numero_iscrizione asc')
        hash_attesa_precedente = HASH_ZERO
        rotture = []
        for r in record_ordinati:
            hash_atteso = r._calcola_hash_da_self()
            if r.hash_precedente != hash_attesa_precedente:
                rotture.append((r.numero_iscrizione,
                                'hash_precedente diverso da atteso'))
            if r.hash_record != hash_atteso:
                rotture.append((r.numero_iscrizione,
                                'hash_record non corrisponde ai dati'))
            hash_attesa_precedente = r.hash_record
        if rotture:
            primo_n, primo_msg = rotture[0]
            raise UserError(_(
                "Catena di integrita' rotta al record n. %s: %s. "
                "Possibile manomissione del DB. Totale anomalie: %d."
            ) % (primo_n, primo_msg, len(rotture)))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Catena integra"),
                'message': _("Verificati %d record. Hash chain valida.") % len(record_ordinati),
                'type': 'success',
                'sticky': False,
            },
        }

    # ----------------- WRITE-ONCE -----------------

    _CAMPI_WRITE_ONCE = frozenset({
        'numero_iscrizione', 'nome', 'cognome', 'codice_fiscale',
        'data_nascita', 'luogo_nascita',
        'indirizzo_residenza', 'cap_residenza',
        'citta_residenza', 'provincia_residenza',
        'tipo', 'data_inizio_attivita', 'attivita_svolta',
        'consenso_privacy_data', 'hash_record', 'hash_precedente',
    })

    def write(self, vals):
        violazioni = set(vals.keys()) & self._CAMPI_WRITE_ONCE
        if violazioni:
            raise UserError(_(
                "Il registro dei volontari e' inalterabile per legge "
                "(DM 6 ottobre 2021). Campi non modificabili: %s. "
                "Per correggere un errore, annullare la riga e crearne "
                "una nuova."
            ) % ", ".join(sorted(violazioni)))
        # data_fine_attivita: modificabile solo se attualmente vuota.
        if 'data_fine_attivita' in vals and vals['data_fine_attivita']:
            for rec in self:
                if rec.data_fine_attivita:
                    raise UserError(_(
                        "La data di fine attivita' di '%s' e' gia' "
                        "valorizzata e non puo' essere modificata. "
                        "Per riprendere il volontariato, creare una "
                        "nuova iscrizione."
                    ) % rec.display_name)
        return super().write(vals)

    def unlink(self):
        raise UserError(_(
            "Il registro dei volontari non ammette cancellazioni. "
            "Per correggere un errore, usa 'Annulla iscrizione' con "
            "motivazione."
        ))

    # ----------------- vidimazione: check pre-create -----------------

    @api.model
    def _verifica_vidimazione_recente(self):
        """Art. 2215-bis cc: se l'ultima vidimazione e' precedente di
        oltre 12 mesi, la nuova iscrizione deve essere preceduta da
        una vidimazione. Per la prima iscrizione in assoluto NON
        richiediamo vidimazione (catena vuota = catena valida)."""
        Vid = self.env['crocevia.registro.vidimazione']
        ultima = Vid.search(
            [('stato', '=', 'firmato_verificato')],
            order='marca_temporale_data desc', limit=1)
        # Se mai vidimato e ci sono gia' iscrizioni, e' un'eccezione
        # storica (transition). Se mai vidimato e niente iscrizioni,
        # la prima entra senza problemi.
        if not ultima and self.search_count([]) == 0:
            return
        if not ultima:
            # Iscrizioni presenti senza alcuna vidimazione: blocca.
            raise UserError(_(
                "Per registrare nuovi volontari occorre prima vidimare "
                "lo stato corrente del registro (art. 2215-bis cc). "
                "Vai in 'Vidimazioni' e completa il flusso firma."
            ))
        from datetime import timedelta
        soglia = fields.Datetime.now() - timedelta(days=366)
        if ultima.marca_temporale_data and ultima.marca_temporale_data < soglia:
            raise UserError(_(
                "L'ultima vidimazione e' del %s, piu' di 12 mesi fa. "
                "Per legge (art. 2215-bis cc) prima di nuove iscrizioni "
                "occorre rividimare il registro."
            ) % ultima.marca_temporale_data.strftime('%d/%m/%Y'))
