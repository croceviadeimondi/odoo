# Odoo - Crocevia dei Mondi APS

Installazione self-hosted di **Odoo 18 Community** per la gestione di
**tesseramento** (libro soci, quote, cariche direttive, verbali) e
**contabilita'** dell'associazione di promozione sociale Crocevia dei Mondi.

Il **sito pubblico** vive a parte (repo `croceviadeimondi/sito`, Astro
statico + Directus CMS, deploy su `croceviadeimondi.org`): qui Odoo fa
solo da backend gestionale e da API per ricevere le richieste di
tesseramento.

## Stack

- Odoo 18.0 Community (immagine Docker ufficiale)
- PostgreSQL 16
- Orchestrazione via Docker Compose

## Prerequisiti

- Docker + plugin Compose (su Arch: `sudo pacman -S docker-compose`)

## Primo avvio

1. **Crea i file di configurazione locali** (non sono nel repo perche'
   contengono password):

   ```sh
   cp .env.example .env
   cp config/odoo.conf.example config/odoo.conf
   ```

2. **Imposta le password**, sostituendo i segnaposto:
   - `.env` -> `DB_PASSWORD` (password del database)
   - `config/odoo.conf` -> `admin_passwd` (master password di Odoo)

3. **Avvia i container:**

   ```sh
   docker compose up -d
   ```

4. Apri **http://localhost:8069**. Alla prima apertura Odoo chiede la
   master password e crea il database. Usa il nome `crocevia`, paese
   Italia (carica il piano dei conti italiano), niente dati demo.

## Comandi utili

```sh
docker compose logs -f odoo     # log Odoo
docker compose restart odoo     # riavvia (dopo modifiche agli addons)
docker compose down             # ferma tutto (i dati restano nei volumi)
docker compose pull             # aggiorna le immagini Docker
```

## Moduli Odoo da installare per un'APS/ETS

Dall'interfaccia di Odoo, menu App, installa direttamente il modulo
**Crocevia dei Mondi - Tesseramento** (in `addons/crocevia_tesseramento/`):
tira giu' in cascata le sue dipendenze (`contacts`, `mail`, `membership`,
`account`).

Per la localizzazione italiana, in fase di creazione del database scegli
**Italia** come paese: Odoo carica il piano dei conti italiano.

## Struttura del repo

```
.
├── docker-compose.yml              definizione servizi Odoo + PostgreSQL
├── .env.example                    template variabili (gitignored una volta copiato)
├── config/
│   └── odoo.conf.example           template config Odoo (gitignored una volta copiato)
└── addons/
    └── crocevia_tesseramento/      modulo custom (registro soci, cariche, API)
```

## Roadmap

- [x] Infrastruttura Docker (Odoo 18 + PostgreSQL)
- [x] Modulo custom [`crocevia_tesseramento`](addons/crocevia_tesseramento/README.md):
      registro soci, cariche direttive con storico, API per richieste di
      tesseramento dal sito, archivio verbali
- [ ] Creazione database `crocevia` e installazione del modulo
- [ ] Configurazione tesseramento: prodotto quota associativa 2026
      (10 EUR, anno solare), allineamento sequenza numero socio col libro
      cartaceo, inserimento delle 4 cariche del direttivo attuale
- [ ] Configurazione contabilita': giornali Cassa/Banca, piano dei conti
      italiano, conti dedicati (Quote associative, Erogazioni liberali)
- [ ] Form di tesseramento sul sito (repo `sito`, pagina `/tesserati/`)
      che POSTa a `https://<odoo>/api/iscrizione`
- [ ] Import elenco soci esistente
- [ ] Reverse proxy HTTPS su sottodominio (es.
      `gestionale.croceviadeimondi.org`) + backup periodico

## Note

I file `.env`, `config/odoo.conf` e i volumi dati non sono versionati:
contengono segreti o dati locali. Per un nuovo ambiente bastano i passi
del primo avvio.
