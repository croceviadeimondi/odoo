# Dati da raccogliere per il setup di Odoo

Checklist dei dati ancora da inserire nel gestionale. Spuntare man mano.
Quando un blocco e' completo, comunicare in conversazione cosi' il valore
viene salvato nei parametri di sistema o nei record relativi.

> **NB**: gran parte dei dati anagrafici dell'APS (denominazione, CF,
> P.IVA, RUNTS, IBAN, Satispay URL, logo, sedi, direttivo) **sono gia'
> nel CMS del sito** (Directus, collection `impostazioni`, `sedi`,
> `direttivo_membri`). L'idea e' di **sincronizzarli da li'** una volta
> sola al primo setup, e non duplicarli a mano. Vedi sezione finale
> "Sincronizzazione dal CMS del sito".

---

## 1. Importi standard (parametri di sistema)

Da scolpire come default nel modulo `crocevia_tesseramento`. Tutti
modificabili in seguito senza redeploy (Impostazioni > Tecnico >
Parametri di sistema).

- [x] **Obolo giornaliero**: 2 EUR (gia' confermato)
- [ ] **Contributo mensile** standard: EUR ___
- [ ] **Quota associativa annuale** (se esiste come voce separata):
      EUR ___, oppure indicare "non applicabile, solo mensilita'/obolo"
- [ ] **Contributo evento**: range 3-5 EUR confermato, default per il
      bottone "Evento" sulla scheda socio: EUR ___ (modificabile al
      volo nel popup)

## 2. Anagrafica privata dei 4 direttivi

I 4 partner sono gia' creati con nome e numero socio (1-4). I dati
pubblici (foto, ruolo, bio) sono nel CMS del sito ed eventualmente si
sincronizzano. I dati **riservati** invece servono solo a Odoo (registro
soci, comunicazioni RUNTS, eventuali ricevute personali):

Per ciascuno dei 4:

### Presidente: Nino Tarantino (numero socio 1)
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza (via, CAP, citta', provincia)
- [x] Email personale (`alderan87@yahoo.it`)
- [ ] Telefono

### Vicepresidente: Eleonora Ghizzota (numero socio 2)
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza
- [x] Email personale (`angelica.ghizzota@gmail.com`)
- [ ] Telefono

### Segretario: Lele Damato (numero socio 3) — l'utente
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza
- [x] Email (`ggdamato@outlook.it`)
- [ ] Telefono

### Tesoriere: Fabrizio Zingrillo (numero socio 4)
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza
- [x] Email personale (`ziofabr@gmail.com`)
- [ ] Telefono

## 3. Verbale assemblea elettiva del direttivo

Le cariche `crocevia.carica` sono da creare con `data_nomina` corretta.

- [ ] **Data dell'assemblea elettiva** che ha nominato l'attuale
      direttivo (formato YYYY-MM-DD)
- [ ] **Numero verbale** o riferimento univoco (es. "Verbale n.3/2025")
- [ ] **File PDF del verbale** (da allegare al record
      `crocevia.verbale` di tipo `assemblea_soci`)

## 4. Sistemi di pagamento non gestiti dal CMS

Satispay e' gia' nel CMS (campo `satispay_charity_url` della collection
`impostazioni`). Restano:

- [ ] **Account PayPal**: email del PayPal Business dell'APS (per
      tracciare le entrate; le commissioni si registrano come uscita
      contabile)
- [ ] **Altri metodi**: SumUp / Stripe / Mollie attivi? In quale ordine
      di priorita' come alternativa a PayPal?

## 5. Inventario beni (Google Sheet)

L'inventario attuale e' in un Google Sheet. Per importarlo in Odoo:

- [ ] **URL del Google Sheet** o **export CSV** (preferibilmente CSV
      perche' l'importer di Odoo lo digerisce direttamente)
- [ ] Verificare che le colonne contengano almeno:
  - `name` (titolo del bene)
  - `categoria` (libro / gioco da tavolo / gioco di ruolo / manuale /
    altro)
  - `sede` (nome citta' della sede, deve esistere in Odoo prima
    dell'import — Barletta / Trani gia' previste)
  - eventuali: `codice_interno`, `autore`, `editore`,
    `anno_pubblicazione`, `isbn`, `valore_stimato`, `note`
- [ ] Se i nomi delle colonne nel Sheet sono diversi, la mappatura si
      fa al momento dell'import (drag & drop)

## 6. Servizio civile (in pianificazione)

Dato non urgente, ma utile averlo presente quando partira'.

- [ ] **Data prevista accensione** del progetto SCU al Crocevia
- [ ] **Numero di volontari SCU previsti**
- [ ] **Codice progetto SCU** (assegnato dal Dipartimento Politiche
      Giovanili al momento dell'approvazione)
- [ ] **Tutor/OLP designati** tra i soci

## 7. Soci esistenti (i ~76 oltre al direttivo)

Per popolare il registro completo:

- [ ] **Elenco soci attivi** (export o foglio Excel/CSV con: nome,
      cognome, CF, email, telefono, data iscrizione)
- [ ] Per ciascuno: categoria (volontario / amministrativo / onorario)
- [ ] Per i pagamenti gia' incassati per il 2026: storico (data,
      importo, metodo) — opzionale, si puo' partire da zero col modulo
      nuovo

---

## Sincronizzazione dal CMS del sito (Directus)

Il sito del Crocevia (`croceviadeimondi.org`, repo `sito` parallelo)
contiene gia' su Directus i dati anagrafici dell'APS. Endpoint API
pubblico: `https://cms.croceviadeimondi.org/items/{collection}`.

Da importare in Odoo una sola volta al setup:

### Da `impostazioni` (singleton) -> `res.company` "Crocevia dei Mondi APS"
| Campo Directus | Campo Odoo |
|---|---|
| `denominazione_completa` | `res.company.name` |
| `codice_fiscale` | `res.company.vat` o campo CF dedicato |
| `partita_iva` | `res.company.vat` (se attiva) |
| `numero_runts` | parametro `crocevia.runts_numero` |
| `email_principale` | `res.company.email` |
| `telefono` | `res.company.phone` |
| `iban_donazioni` | parametro `crocevia.iban` |
| `intestatario_iban` | parametro `crocevia.iban_intestatario` |
| `satispay_charity_url` | parametro `crocevia.satispay_url` |
| `logo_principale` | `res.company.logo` (download da Directus) |

### Da `sedi` -> `crocevia.sede` (modello in pianificazione)
| Campo Directus | Campo Odoo |
|---|---|
| `citta` | `crocevia.sede.citta` |
| `indirizzo_completo` | parsing in via/civico/cap |
| `is_sede_legale` | flag opzionale `is_sede_legale` |

Sedi attuali da inserire come dati iniziali del modulo
`crocevia_inventario`:
- **Barletta** — Via Alfieri 9
- **Trani** — Via Mario Pagano 78

### Da `direttivo_membri` -> integrazione `res.partner` dei 4 direttivi
| Campo Directus | Campo Odoo |
|---|---|
| `name` | gia' presente (matching per nome) |
| `photo` (FK Directus files) | `res.partner.image_1920` (download) |
| `bio` | `res.partner.comment` o campo dedicato |
| `role` | non importato (la carica e' in `crocevia.carica`) |

### Implementazione

Server action di Odoo "Sincronizza dati anagrafici dal sito" che:
1. `requests.get('https://cms.croceviadeimondi.org/items/impostazioni')`
2. Aggiorna `res.company` corrente
3. Imposta i parametri di sistema `crocevia.*`
4. Scarica e imposta logo
5. Ripete per sedi e direttivo

Modulo `crocevia_sync` (in pianificazione) ospitera' questa logica.

---

## Come aggiornare questo file

Quando un dato e' disponibile:
1. Comunicarlo in chat con riferimento alla sezione.
2. Il valore viene inserito nei parametri di sistema o nei record
   pertinenti.
3. La checkbox viene spuntata da `[ ]` a `[x]`.
4. Eventualmente si rimuove la riga se non e' piu' rilevante.
