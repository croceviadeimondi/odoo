# Crocevia dei Mondi - Registro Volontari

Registro dei volontari conforme al **DM 6 ottobre 2021** e all'**art. 2215-bis
del Codice Civile** (libri sociali tenuti con strumenti informatici:
inalterabilita', numerazione progressiva, vidimazione annuale con firma
elettronica + marca temporale).

## Impianto

- **`crocevia.registro.iscrizione`** - l'iscrizione di un volontario nel
  registro legale. Snapshot anagrafico *write-once* (immutabile dopo la
  vidimazione). Numerazione progressiva via `ir.sequence`, mai riusata.
- **Hash chain SHA-256**: ogni record vidimato concatena l'hash del precedente
  (`hash_precedente` + `hash_record`). Una manomissione del DB rompe la catena
  ed e' rilevabile con il bottone *Verifica integrita'* (`action_verifica_catena`).
- **`crocevia.registro.vidimazione`** - l'atto di vidimazione: genera uno
  **snapshot PDF deterministico** (weasyprint + qpdf), il responsabile lo firma
  e marca **esternamente**, lo ricarica e il modulo lo **verifica
  crittograficamente** (vedi sotto). Alla chiusura i record in bozza vengono
  congelati (hash chain) e diventano immutabili.
- Modello **"bozza fino a vidimazione"**: in bozza i record sono modificabili
  (audit nel chatter); dopo la vidimazione sono bloccati da override di
  `write`/`unlink` (vincolo anche per superuser).
- Workflow di **annullamento** (mai cancellazione), wizard cessazione ed
  **export CSV** per la compagnia assicurativa, **cron reminder** annuale.

## Verifica firma (v2.0)

All'upload del PDF firmato, `action_verifica_firma` usa **pyHanko**
(`utils/verifica_pades.py`) per verificare:

1. **integrita'** della firma PAdES (documento non modificato dopo la firma);
2. **validita' crittografica** della firma;
3. **copertura** dell'intero documento;
4. presenza della **marca temporale RFC 3161** (data certa).

Questi requisiti sono **sempre obbligatori**. I campi `firma_valida`,
`firmatario_nome/cf`, `marca_temporale_data`, `tsa_provider`, `firma_dettagli`
sono compilati automaticamente dall'esito (read-only). Se la verifica fallisce,
la vidimazione va in stato `errore` e non viene chiusa.

### Firma qualificata (catena CA) - opzionale

L'asserzione che la firma sia **qualificata** richiede la validazione della
catena del certificato contro le CA qualificate (trust list AgID/EU). E'
**best-effort**:

- metti i certificati CA (PEM/CRT) in `data/trust/` (vedi `data/trust/README.txt`);
- attiva il parametro di sistema `crocevia_registro_volontari.firma_strict =
  True` per **richiedere** la catena qualificata ai fini della validita'.

Fonte trust list: EU Trusted List / TSL italiana AgID
(`https://eidas.agid.gov.it/TL/TSL-IT.xml`), da aggiornare periodicamente.

## Firma esterna (procedura operativa)

1. In una vidimazione, *Genera snapshot* -> scarica il PDF "da firmare".
2. Firmalo con il tuo software (ArubaSign / GoSign / Dike / Namirial) con
   **firma elettronica qualificata (FEQ) + marca temporale (PAdES-T)**.
3. Ricarica il PDF firmato e clicca *Verifica firma*.

## Test

`docker compose run --rm odoo odoo -d crocevia -u crocevia_registro_volontari
--test-enable --stop-after-init --no-http`

Coprono: hash chain + ricalcolo, rilevamento manomissione, write-once,
congelamento, unicita' CF, verificatore PAdES (casi negativi). Il percorso
positivo della firma (PDF firmato valido) va provato manualmente con una firma
reale.
