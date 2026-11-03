# crocevia_miniapp

Backend Odoo della sezione **Inventario** della miniapp Telegram (la stessa
delle prenotazioni delle stanze). La spec sta in
`md direzionali/cdm-miniapp-inventario-spec.md`.

## Cosa aggiunge

- `res.partner.telegram_id`, univoco, nella pagina Socio di tutte e due le
  schede. Si scrive quando lo staff conferma un socio dal gruppo Telegram, e si
  puo' correggere a mano.
- `res.partner.miniapp_privacy_data`: quando il socio ha accettato
  l'informativa dalla miniapp.
- Utente tecnico **Miniapp Telegram** (login `miniapp`, senza password) col
  solo gruppo "Miniapp Telegram (utente tecnico)".
- Modello astratto `crocevia.miniapp`: i metodi che il server della miniapp
  chiama via XML-RPC.

I soci **non** diventano utenti Odoo: nasce o si aggancia solo la scheda.

## Regole

| parametro di sistema | default | cosa fa |
|---|---|---|
| `crocevia_miniapp.giorni_prestito` | 30 | durata di un prestito, e di un prolungamento |
| `crocevia_miniapp.max_prestiti` | 1 | prestiti aperti per socio |

Valgono solo per i prestiti aperti dalla miniapp. Da Odoo lo staff resta
libero di fare eccezioni.

## Metodi

| metodo | chi | cosa |
|---|---|---|
| `socio_da_telegram(telegram_id)` | tutti | la scheda, o False se non e' socio (o e' cessato) |
| `candidati(nome, cognome)` | staff | soci senza Telegram con nome simile |
| `collega_socio(telegram_id, partner_id, privacy_data, da_chi)` | staff | "e' lui" |
| `crea_socio(telegram_id, nome, cognome, privacy_data, da_chi)` | staff | "socio nuovo", stato Richiesta |
| `opzioni()` | tutti | sedi, categorie, generi, sistemi, regole |
| `catalogo(filtri, offset, limit, staff)` | soci | beni; chi ha il bene solo con `staff=True` |
| `bene(bene_id, staff)` | soci | un bene |
| `presta(telegram_id, bene_id, note)` | soci | apre il prestito |
| `miei_prestiti(telegram_id)` | soci | prestiti aperti |
| `restituisci(telegram_id, prestito_id)` | soci | solo i propri |
| `prolunga(prestito_id, giorni, da_chi)` | staff | da oggi se gia' scaduto |
| `scaduti()` | bot | per i promemoria del lunedi |
| `stesso_isbn(isbn, sede_id)` | staff | doppioni, trattini a parte |
| `cerca_soci(testo)` | staff | per il proprietario di un bene |
| `crea_genere(nome)`, `crea_sistema(nome)` | staff | senza doppioni di maiuscole |
| `crea_bene(valori, da_chi)` | staff | solo i campi del form |

"Chi" lo decide il server della miniapp, che verifica l'initData di Telegram
e sa chi sta nei gruppi staff. Odoo controlla solo che a chiamare sia l'utente
tecnico: un Membro che chiama questi metodi via RPC riceve un AccessError.

Ogni azione lascia una nota interna nel chatter (del socio, del prestito o del
bene), con chi l'ha fatta.

## Messa in funzione

1. `-i crocevia_miniapp`.
2. Impostazioni > Utenti > Miniapp Telegram > Sicurezza account > nuova chiave
   API. Va nella config del server del calendario, non nel repo.

## Test

```sh
docker compose run --rm -T odoo odoo -d <db di prova> -i crocevia_miniapp \
    --test-tags /crocevia_miniapp --stop-after-init --no-http
```

Su un DB vuoto non si installa: `crocevia_tesseramento` si rompe prima
(vedi sotto). Si prova su una copia del DB locale.

## Noto

`crocevia_tesseramento` non si installa su un database nuovo: in
`views/res_partner_views.xml` la lista del Libro soci usa
`%(action_unifica_soci)d` prima che l'azione sia caricata. Sui DB esistenti
non si vede perche' l'azione c'e' gia'.
