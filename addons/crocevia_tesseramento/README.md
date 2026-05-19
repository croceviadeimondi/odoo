# crocevia_tesseramento

Modulo Odoo 18 per la gestione del tesseramento del Crocevia dei Mondi APS.

## Cosa aggiunge

| Area | Contenuto |
|---|---|
| Soci | Estende `res.partner`: `numero_socio` progressivo, categoria (Amministrativo / Volontario / Onorario / Direttivo), stato (richiesta / attivo / cessato), date di iscrizione e cessazione, tab dedicata sulla scheda contatto. |
| Cariche direttive | Modello `crocevia.carica` con storico mandati per Presidente, Vicepresidente, Segretario, Tesoriere. Vincolo: niente sovrapposizioni di mandato per lo stesso ruolo. |
| API tesseramento | Endpoint `POST /api/iscrizione` che riceve le richieste dal sito esterno (croceviadeimondi.org) e crea record `crocevia.richiesta.iscrizione` da approvare. Il form HTML non sta in Odoo: vive nell'app Astro del sito. |
| Verbali | Modello `crocevia.verbale`: archivio minimo con data, tipo (assemblea soci / riunione direttivo), file allegato. |
| Esenzione onorari | Categoria `onorario` imposta `free_member=True` (campo nativo `membership`), quindi quota associativa non dovuta. |

## Dipendenze

`base`, `contacts`, `mail`, `membership`, `account`.

Nota: NON dipende da `website`. Il sito del Crocevia e' un'app Astro statica
separata (repo `croceviadeimondi/sito`), non un sito Odoo. Odoo qui fa solo
da backend gestionale.

## API: POST /api/iscrizione

Endpoint pubblico per ricevere richieste di tesseramento dal sito.

- Metodo: `POST` (con preflight `OPTIONS` per CORS).
- Content-Type accettati: `application/x-www-form-urlencoded` oppure `application/json`.
- CORS: limitato all'origine definita dal parametro di sistema
  `crocevia_tesseramento.cors_origin` (default `https://croceviadeimondi.org`).
  Modificabile da Impostazioni - Tecnico - Parametri di sistema.
- Anti-spam: honeypot (campo nascosto `website` da non compilare lato form).
- Risposta: JSON `{"success": true, "message": "..."}` (200) oppure
  `{"success": false, "error": "..."}` (400/500).

Campi accettati:

| Campo | Tipo | Obbligatorio |
|---|---|---|
| `nome` | string | si |
| `cognome` | string | si |
| `email` | string | si |
| `consenso_privacy` | bool/truthy | si |
| `telefono` | string | no |
| `data_nascita` | string YYYY-MM-DD | no |
| `luogo_nascita` | string | no |
| `codice_fiscale` | string 16 chars | no |
| `indirizzo` | string | no |
| `cap` | string 5 chars | no |
| `citta` | string | no |
| `provincia` | string 2 chars | no |
| `categoria_richiesta` | `volontario` o `amministrativo` | no (default volontario) |
| `messaggio` | string | no |

Esempio chiamata da JavaScript (sito Astro):

```js
const data = new FormData(formElement);
const res = await fetch('https://gestionale.croceviadeimondi.org/api/iscrizione', {
  method: 'POST',
  body: data,
});
const out = await res.json();
if (out.success) { /* mostra grazie */ } else { /* mostra out.error */ }
```

## Installazione

Dopo aver montato `addons/` in Odoo (gia' configurato nel docker-compose del repo):

1. Attiva la modalita' sviluppatore.
2. Vai in App, rimuovi il filtro "Apps", aggiorna la lista.
3. Cerca "Crocevia" e installa: tira giu' in cascata `membership`, `account`, `mail`, `contacts`.
4. Assegna i membri del direttivo al gruppo "Direttivo Crocevia"
   da Impostazioni - Utenti.

## Sequenza numero socio

Il modulo crea la sequenza `crocevia.numero.socio` (numerica semplice,
parte da 1). Per allineare al libro soci cartaceo esistente:
Impostazioni - Tecnico - Sequenze - Numero socio Crocevia, e modificare
"Numero successivo".

## Direttivo CDM (al 2026-05-19)

Da inserire manualmente come cariche dopo l'attivazione dei soci
corrispondenti:

- Presidente: Nino Tarantino
- Vicepresidente: Eleonora Ghizzota
- Segretario: Lele Damato
- Tesoriere: Fabrizio Zingrillo

Le date di nomina vanno prese dai verbali delle assemblee di elezione.
