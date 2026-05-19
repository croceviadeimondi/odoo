# Odoo — Crocevia dei Mondi APS

Installazione self-hosted di **Odoo 18 Community** per la gestione di
**tesseramento** (libro soci, quote associative) e **contabilità**
dell'associazione di promozione sociale Crocevia dei Mondi.

## Stack

- **Odoo 18.0 Community** — immagine Docker ufficiale
- **PostgreSQL 16**
- Orchestrazione via **Docker Compose**

## Prerequisiti

- Docker + Docker Compose installati sul server (o sul PC che farà da host)

## Primo avvio

1. **Crea i file di configurazione locali** (non sono nel repo perché
   contengono password):

   ```sh
   cp .env.example .env
   cp config/odoo.conf.example config/odoo.conf
   ```

2. **Imposta le password** — modifica:
   - `.env` → `DB_PASSWORD` (password del database)
   - `config/odoo.conf` → `admin_passwd` (master password di Odoo)

   Usa password lunghe e casuali per entrambe.

3. **Avvia i container:**

   ```sh
   docker compose up -d
   ```

4. Apri **http://localhost:8069** (o l'IP del server sulla porta scelta).
   Alla prima apertura Odoo chiede di creare il database: usa il nome
   `crocevia` e imposta l'account amministratore.

## Comandi utili

```sh
docker compose logs -f odoo     # vedi i log di Odoo
docker compose restart odoo     # riavvia dopo modifiche agli addons
docker compose down             # ferma tutto (i dati restano nei volumi)
docker compose pull             # aggiorna le immagini Docker
```

## Moduli Odoo da installare per un'APS/ETS

Dall'interfaccia di Odoo (menu **App**), installa:

| Modulo            | A cosa serve                                              |
|-------------------|-----------------------------------------------------------|
| **Contatti**      | Anagrafica soci                                           |
| **Membri** (`membership`) | Tessere, quote associative, scadenze tesseramento |
| **Contabilità**   | Prima nota, registrazioni, bilancio                       |
| **Fatturazione**  | Ricevute per le quote / erogazioni liberali               |

Per la localizzazione italiana, in fase di creazione del database scegli
**Italia** come paese: Odoo carica il piano dei conti italiano.

## Struttura del repo

```
.
├── docker-compose.yml        # definizione dei servizi Odoo + PostgreSQL
├── .env.example              # template variabili d'ambiente (→ copia in .env)
├── config/
│   └── odoo.conf.example     # template config Odoo (→ copia in odoo.conf)
└── addons/                   # moduli custom del Crocevia (montati in Odoo)
```

## Roadmap

- [x] Infrastruttura Docker (Odoo 18 + PostgreSQL)
- [x] Modulo custom **[`crocevia_tesseramento`](addons/crocevia_tesseramento/README.md)**:
      registro soci con numero progressivo e categoria, cariche direttive con
      storico mandati, form pubblico di richiesta iscrizione, archivio verbali
- [ ] Creazione database `crocevia` e configurazione iniziale (UI Odoo)
- [ ] Configurazione tesseramento: prodotto quota associativa 2026 (10 €,
      anno solare), allineamento sequenza numero socio col libro cartaceo
- [ ] Configurazione contabilità: giornali Cassa/Banca, piano dei conti
      italiano, conti dedicati (Quote associative, Erogazioni liberali)
- [ ] Pubblicazione voce di menu "Iscriviti" sul sito (→ `/iscrizione`)
- [ ] Import elenco soci esistente dal foglio di calcolo
- [ ] Reverse proxy HTTPS + backup periodico (prima del go-live pubblico)

## Note

I file `.env`, `config/odoo.conf` e i volumi dati **non sono versionati**:
contengono segreti o dati locali. Per un nuovo ambiente bastano i passi
del "Primo avvio".
