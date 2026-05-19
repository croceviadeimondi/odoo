# `crocevia_tesseramento` — Modulo custom

Modulo Odoo 18 per la gestione del tesseramento del Crocevia dei Mondi APS.

## Cosa aggiunge

| Area | Contenuto |
|---|---|
| **Soci** | Estende `res.partner`: `numero_socio` progressivo, categoria (Amministrativo / Volontario / Onorario / Direttivo), stato (richiesta / attivo / cessato), date di iscrizione e cessazione, tab dedicata sulla scheda contatto. |
| **Cariche direttive** | Modello `crocevia.carica` con storico mandati per Presidente, Vicepresidente, Segretario, Tesoriere. Vincolo: niente sovrapposizioni di mandato per lo stesso ruolo. |
| **Richieste online** | Form pubblico su `/iscrizione` → modello `crocevia.richiesta.iscrizione`. Il direttivo approva → viene creato un `res.partner` socio attivo con numero progressivo. |
| **Verbali** | Modello `crocevia.verbale`: archivio minimo con data, tipo (assemblea soci / riunione direttivo), file allegato. |
| **Esenzione onorari** | Categoria `onorario` → imposta `free_member=True` (campo nativo `membership`) → quota associativa non dovuta. |

## Dipendenze

`base`, `contacts`, `mail`, `membership`, `account`, `website`.

## Installazione

Dopo aver montato `addons/` in Odoo (già configurato nel docker-compose del repo):

1. Attiva la modalità sviluppatore.
2. Vai in **App**, rimuovi il filtro "Apps", aggiorna la lista.
3. Cerca "Crocevia" e installa.
4. Assegna i membri del direttivo al gruppo **Direttivo Crocevia**
   (Impostazioni → Utenti).

## Sequenza numero socio

Il modulo crea la sequenza `crocevia.numero.socio` (numerica semplice, parte da 1).
Per allineare al libro soci cartaceo esistente: **Impostazioni → Tecnico →
Sequenze → Numero socio Crocevia** e modificare "Numero successivo".

## Form pubblico

Una volta installato il modulo, la rotta `/iscrizione` è attiva sul sito.
Aggiungi una voce di menu "Iscriviti" che punta a `/iscrizione` dall'editor del
sito.
