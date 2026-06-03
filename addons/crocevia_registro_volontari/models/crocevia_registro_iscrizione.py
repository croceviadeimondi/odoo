"""
Modello `crocevia.registro.iscrizione`: una riga del registro volontari.

Modello "alterabile fino alla vidimazione" (v1.1, allineato alla prassi
dei libri contabili ex art. 2215-bis cc):

1. **Stato `bozza`**: subito dopo `create`, il record e' modificabile e
   cancellabile come un normale record Odoo. Il chatter traccia ogni
   modifica (audit log) ma il record stesso non e' ancora "fissato".
2. **Stato `vidimato`**: quando il responsabile chiude una vidimazione
   (firma + marca temporale sul PDF snapshot), tutti i record in `bozza`
   vengono congelati: la `write()` blocca modifiche ai campi anagrafici,
   la `unlink()` lancia errore, e in quel momento si calcola la
   **hash chain** SHA-256 (`hash_record` + `hash_precedente`) cosi' la
   catena rappresenta lo stato consolidato del registro alla data di
   vidimazione. Manomissioni SQL successive vengono rilevate da
   "Verifica catena".
3. **Numerazione progressiva mai riusata**: anche se un record viene
   cancellato in bozza o annullato dopo la vidimazione, il numero
   resta occupato. La sequenza `crocevia.registro.volontario` non e'
   reversibile.
4. **Data di apposizione**: il significato di "data certa" del DM
   6/10/2021 e' soddisfatto dalla marca temporale sulla vidimazione
   (RFC 3161 PAdES-T) che congela lo stato del registro alla data X.
   Pre-vidimazione: chatter Odoo per l'audit. Post-vidimazione:
   inalterabilita' enforced.

Questo allineamento richiede vidimazione **almeno annuale** (art.
2215-bis cc): il cron mensile + il gate sul `create` (>12 mesi senza
vidimare = blocco) lo garantiscono.
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

STATO_INALTERABILITA_SELECTION = [
    ('bozza', 'Bozza (modificabile)'),
    ('vidimato', 'Vidimato (immutabile)'),
]

# Context flag che il codice di vidimazione setta per poter scrivere
# i campi normalmente write-once (hash_record, hash_precedente,
# stato_inalterabilita) durante la chiusura della vidimazione stessa.
CTX_VIDIMAZIONE_IN_CORSO = 'crocevia_vidimazione_in_corso'

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
    stato_inalterabilita = fields.Selection(
        selection=STATO_INALTERABILITA_SELECTION,
        string="Inalterabilita'",
        default='bozza',
        required=True,
        index=True,
        copy=False,
        tracking=True,
        help="In bozza: il record e' modificabile e cancellabile. Una "
             "volta vidimato (firma + marca temporale sulla vidimazione "
             "che lo include nello snapshot), diventa immutabile per "
             "legge (DM 6/10/2021).",
    )

    # Avviso (banner) sullo stato di vidimazione del registro: non stored,
    # uguale per tutti i record, usato per mostrare un alert giallo nelle viste.
    avviso_vidimazione = fields.Char(
        string="Avviso vidimazione",
        compute='_compute_avviso_vidimazione',
    )

    # ----------------- computed -----------------

    @api.depends_context('uid')
    def _compute_avviso_vidimazione(self):
        from datetime import timedelta
        Vid = self.env['crocevia.registro.vidimazione']
        ultima = Vid.search(
            [('stato', '=', 'firmato_verificato')],
            order='marca_temporale_data desc', limit=1)
        avviso = False
        if not ultima or not ultima.marca_temporale_data:
            if self.env['crocevia.registro.iscrizione'].search_count([]):
                avviso = ("Registro mai vidimato: vidimare al piu' presto "
                          "(firma + marca temporale, art. 2215-bis cc).")
        else:
            eta = fields.Datetime.now() - ultima.marca_temporale_data
            if eta > timedelta(days=365):
                avviso = ("Vidimazione SCADUTA (ultima del %s, >12 mesi fa): "
                          "rividimare prima di registrare nuovi volontari."
                          % ultima.marca_temporale_data.strftime('%d/%m/%Y'))
            elif eta > timedelta(days=305):
                avviso = ("Vidimazione in scadenza (ultima del %s): "
                          "pianificare la prossima entro i 12 mesi."
                          % ultima.marca_temporale_data.strftime('%d/%m/%Y'))
        for r in self:
            r.avviso_vidimazione = avviso

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
        # Gate art. 2215-bis cc: blocca nuovi inserimenti se l'ultima
        # vidimazione e' >12 mesi fa (vidimazione annuale obbligatoria).
        self._verifica_vidimazione_recente()

        Sequence = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('codice_fiscale'):
                vals['codice_fiscale'] = vals['codice_fiscale'].upper().strip()
            # Numero progressivo dalla sequenza, mai riusato.
            if not vals.get('numero_iscrizione'):
                next_n = Sequence.next_by_code('crocevia.registro.volontario')
                vals['numero_iscrizione'] = int(next_n) if next_n else 1
            # Stato inalterabilita': default 'bozza'. Hash chain calcolata
            # solo al momento della vidimazione, non qui.
            vals.setdefault('stato_inalterabilita', 'bozza')
        return super().create(vals_list)

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
        """Ricalcola gli hash della catena dei record vidimati e mostra
        il primo punto di rottura, se esiste. I record in bozza non
        partecipano alla catena (la catena viene costruita solo alla
        vidimazione)."""
        record_ordinati = self.search(
            [('stato_inalterabilita', '=', 'vidimato')],
            order='numero_iscrizione asc',
        )
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
        n_bozza = self.search_count([('stato_inalterabilita', '=', 'bozza')])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Catena integra"),
                'message': _(
                    "Verificati %d record vidimati. Hash chain valida. "
                    "%d record in bozza (non ancora vidimati: saranno "
                    "congelati alla prossima vidimazione)."
                ) % (len(record_ordinati), n_bozza),
                'type': 'success',
                'sticky': False,
            },
        }

    def _congela_bozza_per_vidimazione(self):
        """Chiamato dalla `crocevia.registro.vidimazione.action_verifica_firma`
        quando una vidimazione viene chiusa. Trova tutti i record in
        stato 'bozza' e li congela:
        - calcola hash_record e hash_precedente
        - setta stato_inalterabilita='vidimato'
        Restituisce il numero di record congelati."""
        Isc = self.with_context(**{CTX_VIDIMAZIONE_IN_CORSO: True})
        bozza = Isc.search(
            [('stato_inalterabilita', '=', 'bozza')],
            order='numero_iscrizione asc',
        )
        if not bozza:
            return 0
        # Trovo l'ultimo record vidimato per partire la catena.
        ultimo_vidimato = Isc.search(
            [('stato_inalterabilita', '=', 'vidimato')],
            order='numero_iscrizione desc', limit=1,
        )
        prev_hash = ultimo_vidimato.hash_record if ultimo_vidimato else HASH_ZERO

        for rec in bozza:
            # Calcolo hash usando il payload corrente del record +
            # l'hash precedente. Devo simulare i vals.
            vals_hash = {
                k: rec[k] if k != 'hash_precedente' else prev_hash
                for k in rec._campi_in_hash()
            }
            new_hash = rec._calcola_hash_da_vals(vals_hash)
            rec.write({
                'hash_precedente': prev_hash,
                'hash_record': new_hash,
                'stato_inalterabilita': 'vidimato',
            })
            prev_hash = new_hash
        return len(bozza)

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
        # Bypass per il codice di vidimazione che deve scrivere
        # hash_record, hash_precedente, stato_inalterabilita al momento
        # della chiusura della vidimazione stessa.
        if self.env.context.get(CTX_VIDIMAZIONE_IN_CORSO):
            return super().write(vals)

        # Per i record vidimati: applichiamo il write-once classico.
        record_vidimati = self.filtered(
            lambda r: r.stato_inalterabilita == 'vidimato')
        if record_vidimati:
            violazioni = set(vals.keys()) & self._CAMPI_WRITE_ONCE
            if violazioni:
                raise UserError(_(
                    "Il record n. %s e' gia' stato vidimato (firma + "
                    "marca temporale apposta al registro): non puo' "
                    "essere modificato per legge (DM 6 ottobre 2021). "
                    "Campi non modificabili: %s. Per correggere un "
                    "errore su un record vidimato, usa 'Annulla "
                    "iscrizione' con motivazione."
                ) % (
                    ', '.join('%06d' % r.numero_iscrizione
                              for r in record_vidimati),
                    ", ".join(sorted(violazioni)),
                ))

        # `data_fine_attivita`: una volta valorizzata, non si modifica
        # piu', anche se il record e' ancora in bozza (rappresenta
        # la cessazione dell'attivita', usare wizard ad hoc).
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
        # Record bozza: cancellabili (la numerazione resta occupata,
        # ma il record sparisce). Vidimati: errore.
        bloccati = self.filtered(
            lambda r: r.stato_inalterabilita == 'vidimato')
        if bloccati:
            raise UserError(_(
                "Il/i record n. %s e' gia' vidimato e non puo' essere "
                "cancellato. Per correggere un errore, usa 'Annulla "
                "iscrizione' con motivazione."
            ) % ', '.join('%06d' % r.numero_iscrizione for r in bloccati))
        return super().unlink()

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
