# Dati da raccogliere per il setup di Odoo

Checklist dei dati amministrativi, anagrafici e tecnici ancora da inserire
nel gestionale. Spuntare man mano e annotare la fonte (es. statuto,
verbale, app banca). Quando un blocco e' completo, comunicare in
conversazione cosi' il valore viene salvato nei parametri di sistema o nei
record relativi.

---

## 1. Dati identificativi dell'ente

Servono per intestare ricevute, fatture passive, ricevute di donazione,
report RUNTS. Si configurano in Impostazioni > Aziende > "Crocevia dei
Mondi APS".

- [ ] **Denominazione completa** (statuto, es. "Crocevia dei Mondi APS")
- [ ] **Codice fiscale** dell'ente
- [ ] **Partita IVA** (se attiva, opzionale per APS)
- [ ] **Sede legale**: via, numero civico, CAP, citta', provincia
- [ ] **Sede operativa** (se diversa dalla legale)
- [ ] **Numero iscrizione RUNTS** + data iscrizione
- [ ] **REA** (Repertorio Economico Amministrativo, se presente)
- [ ] **Email istituzionale** (gia' nota: `info@croceviadeimondi.org`,
      confermare se e' anche la mail di intestazione documenti)
- [ ] **PEC** dell'ente
- [ ] **Sito web** (`https://croceviadeimondi.org`, da inserire come
      campo Azienda)

## 2. Dati bancari (per EPC QR Code e fatturazione)

- [ ] **IBAN** del conto intestato all'APS
- [ ] **BIC/SWIFT** della banca (opzionale per SEPA puro, alcune app
      banca lo richiedono nel QR)
- [ ] **Intestatario** esatto come compare sull'estratto conto
- [ ] **Nome banca** (per riferimento ricevute/fatture)

## 3. Importi standard (parametri di sistema)

Da scolpire come default nel modulo `crocevia_tesseramento`. Tutti
modificabili in seguito senza redeploy (Impostazioni > Tecnico >
Parametri di sistema).

- [x] **Obolo giornaliero**: 2 EUR (gia' confermato)
- [ ] **Contributo mensile** standard: EUR ___ (da confermare)
- [ ] **Quota associativa annuale** (se esiste come voce separata):
      EUR ___, oppure indicare "non applicabile, solo mensilita'/obolo"
- [ ] **Contributo evento**: range 3-5 EUR confermato, default per il
      bottone "Evento" sulla scheda socio: EUR ___ (verra' modificabile
      al volo)

## 4. Anagrafica completa dei 4 direttivi

I 4 partner sono gia' creati con nome e numero socio (1-4). Mancano i
dati per completare la scheda contatto e per essere valorizzati nelle
ricevute, comunicazioni RUNTS, registro volontari.

Per ciascuno:

### Presidente: Nino Tarantino (numero socio 1)
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza (via, CAP, citta', provincia)
- [ ] Email personale
- [ ] Telefono

### Vicepresidente: Eleonora Ghizzota (numero socio 2)
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza
- [ ] Email personale
- [ ] Telefono

### Segretario: Lele Damato (numero socio 3) — l'utente
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza
- [ ] Email personale (gia' nota: `ggdamato@outlook.it`?)
- [ ] Telefono

### Tesoriere: Fabrizio Zingrillo (numero socio 4)
- [ ] Codice fiscale
- [ ] Data e luogo di nascita
- [ ] Indirizzo residenza
- [ ] Email personale
- [ ] Telefono

## 5. Verbale assemblea elettiva del direttivo

Le cariche `crocevia.carica` sono da creare con `data_nomina` corretta.

- [ ] **Data dell'assemblea elettiva** che ha nominato l'attuale
      direttivo (formato YYYY-MM-DD)
- [ ] **Numero verbale** o riferimento univoco (es. "Verbale n.3/2025")
- [ ] **File PDF del verbale** (da allegare al record
      `crocevia.verbale` di tipo `assemblea_soci`)

## 6. Identita' grafica

Per i PDF di ricevute, fatture, report RUNTS.

- [ ] **Logo dell'APS** in formato PNG o SVG (preferibilmente sfondo
      trasparente, alta risoluzione)
- [ ] Colori istituzionali (HEX) se vogliamo allinearli al sito Astro

## 7. Sistemi di pagamento

Dati per configurare i metodi accettati nelle ricevute e i collegamenti
contabili.

- [ ] **Account PayPal**: email del PayPal Business dell'APS (per
      tracciare le entrate; le commissioni si registrano come uscita
      contabile)
- [ ] **Satispay for Good**: account business attivato? Numero
      ID/riferimento se gia' creato. Se no, va attivata l'iscrizione
      come ETS sul portale Satispay (richiede certificato RUNTS).
- [ ] **Altri metodi**: SumUp / Stripe / Mollie attivi? In quale ordine
      di priorita' come alternativa a PayPal?

## 8. Servizio civile (in pianificazione)

Dato non urgente, ma utile averlo presente quando partira'.

- [ ] **Data prevista accensione** del progetto SCU al Crocevia
- [ ] **Numero di volontari SCU previsti**
- [ ] **Codice progetto SCU** (assegnato dal Dipartimento Politiche
      Giovanili al momento dell'approvazione)
- [ ] **Tutor/OLP designati** tra i soci

## 9. Soci esistenti (i ~76 oltre al direttivo)

Per popolare il registro completo:

- [ ] **Elenco soci attivi** (export o foglio Excel/CSV con: nome,
      cognome, CF, email, telefono, data iscrizione)
- [ ] Per ciascuno: categoria (volontario / amministrativo / onorario)
- [ ] Per i pagamenti gia' incassati per il 2026: storico (data, importo,
      metodo) — opzionale, si puo' partire da zero col modulo nuovo

---

## Come aggiornare questo file

Quando un dato e' disponibile:
1. Comunicarlo in chat con riferimento alla sezione (es. "sezione 2:
   IBAN IT60X05428 ...").
2. Il valore viene inserito nei parametri di sistema o nei record
   pertinenti.
3. La checkbox viene spuntata da `[ ]` a `[x]`.
4. Eventualmente si rimuove la riga se non e' piu' rilevante.
