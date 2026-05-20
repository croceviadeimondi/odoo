#!/usr/bin/env python3
"""
Trasforma il registro soci del Crocevia (xlsx multi-sheet, una sheet per
anno) in un CSV pronto per essere importato in Odoo.

USO (gira sul TUO PC, non in repo):

    python3 tools/importa_registro_soci.py \\
        --input '/percorso/al/Registro Soci.xlsx' \\
        --output '/tmp/soci_per_odoo.csv' \\
        [--sheet 'Anno 2026']

Se non passi `--sheet` prende l'ultimo (di solito l'anno corrente).

IMPORTANTE - GDPR / art. 622 c.p.:
    Il file `Registro Soci.xlsx` contiene dati personali e sensibili
    (CF, indirizzo, telefono, email, data e luogo di nascita, stato
    civile). Tienilo fuori da questo repo (il `.gitignore` blocca
    `*.xlsx` e `registro_soci*`) e fuori da cartelle cloud non cifrate.
    L'output `soci_per_odoo.csv` va caricato direttamente in Odoo via
    UI e poi cancellato, NON committato.

INTESTAZIONE ATTESA (in ordine, riga 1 o 2 della sheet):
    NOME | COGNOME | DATA DI NASCITA | LUOGO DI NASCITA | INDIRIZZO |
    CITTA' | STATO CIVILE | PROFESSIONE | CODICE FISCALE | TELEFONO |
    E-MAIL | DATA | RUOLO | GENNAIO...DICEMBRE

Le colonne GENNAIO-DICEMBRE (mensilita') NON vengono migrate: per
scelta del direttivo Crocevia il pagamento mensile e' volontario
(salta i mesi in cui il socio non partecipa), quindi importare TRUE
o FALSE retroattivi sarebbe fuorviante. Si parte dal 2026-01-01 in
poi registrando le ricevute man mano.

DIPENDENZA:
    pip install openpyxl

CAVEAT IMPORTANTE - DUPLICATI CON I DIRETTIVI ESISTENTI:
    I 4 direttivi (Tarantino, Ghizzota, Damato, Zingrillo) sono gia'
    creati in Odoo come `res.partner` SENZA codice fiscale. Lo script
    usa l'external id `socio_<CF>` per dedupping/update; quindi
    importando il CSV verranno creati 4 NUOVI partner per i direttivi
    (perche' il vecchio non ha il CF nel suo external id).

    Per evitare duplicati, prima di importare:
    1. apri Odoo > Tesseramento > Soci
    2. apri ciascuno dei 4 direttivi e compila il campo "Codice fiscale"
    3. (opzionale) imposta loro un external id da Settings > Tecnico >
       External Identifiers a `crocevia_tesseramento.socio_<CF>`
    4. ESEGUI L'IMPORT.
    Se invece ti va bene il fix manuale, importa e poi cancella i 4
    duplicati senza CF.

IMPORTAZIONE IN ODOO:
    1. Tesseramento > Soci
    2. menu tre puntini in alto a destra > "Importa records"
    3. Carica `soci_per_odoo.csv`. Odoo riconosce i nomi tecnici delle
       colonne (sono in inglese / nomi dei campi).
    4. Verifica anteprima, conferma.
    5. CANCELLA il file CSV dal tuo PC dopo l'import.
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from openpyxl import load_workbook
except ImportError:
    sys.stderr.write(
        "Manca la libreria openpyxl. Installala con:\n"
        "    pip install openpyxl\n"
    )
    sys.exit(1)


STATO_CIVILE_MAP = {
    'celibe': 'celibe',
    'nubile': 'celibe',
    'coniugato': 'coniugato',
    'coniugata': 'coniugato',
    'sposato': 'coniugato',
    'sposata': 'coniugato',
    'divorziato': 'divorziato',
    'divorziata': 'divorziato',
    'separato': 'divorziato',
    'separata': 'divorziato',
    'vedovo': 'vedovo',
    'vedova': 'vedovo',
}

RUOLO_CATEGORIA_MAP = {
    'presidente': 'direttivo',
    'vicepresidente': 'direttivo',
    'vice presidente': 'direttivo',
    'segretario': 'direttivo',
    'segretaria': 'direttivo',
    'tesoriere': 'direttivo',
    'tesoriera': 'direttivo',
    'consigliere': 'direttivo',
    'consigliera': 'direttivo',
    'volontario': 'volontario',
    'volontaria': 'volontario',
    'amministrativo': 'amministrativo',
    'amministrativa': 'amministrativo',
    'onorario': 'onorario',
    'onoraria': 'onorario',
}


def _parse_data(valore):
    """Da datetime o stringa DD/MM/YYYY (o varianti) a YYYY-MM-DD."""
    if valore is None or valore == '':
        return ''
    if isinstance(valore, datetime):
        return valore.strftime('%Y-%m-%d')
    s = str(valore).strip()
    if not s:
        return ''
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d',
                '%d/%m/%y', '%d.%m.%Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    sys.stderr.write(f"  WARN: data '{s}' non riconosciuta, salto\n")
    return ''


def _stringa(valore):
    if valore is None:
        return ''
    return str(valore).strip()


def _telefono(valore):
    if valore is None:
        return ''
    return re.sub(r'\s+', ' ', str(valore)).strip()


def _email(valore):
    if valore is None:
        return ''
    return str(valore).strip().lower()


def _codice_fiscale(valore):
    if valore is None:
        return ''
    return re.sub(r'\s+', '', str(valore)).upper()


def _stato_civile(valore):
    if not valore:
        return ''
    chiave = str(valore).strip().lower()
    return STATO_CIVILE_MAP.get(chiave, 'altro' if chiave else '')


def _categoria_socio(valore):
    if not valore:
        return ''
    chiave = str(valore).strip().lower()
    return RUOLO_CATEGORIA_MAP.get(chiave, '')


def _scegli_sheet(workbook, nome_richiesto):
    if nome_richiesto:
        if nome_richiesto in workbook.sheetnames:
            return workbook[nome_richiesto]
        sys.stderr.write(
            f"ERRORE: sheet '{nome_richiesto}' non trovato.\n"
            f"Sheet disponibili: {workbook.sheetnames}\n"
        )
        sys.exit(1)
    return workbook[workbook.sheetnames[-1]]


def _trova_riga_intestazione(sheet):
    """Cerca la riga che contiene NOME e COGNOME (di solito 1 o 2,
    a volte 3 se ci sono righe di gruppo come 'ANAGRAFICA | CONTATTI ...')."""
    for row_idx in range(1, 6):
        valori = [sheet.cell(row=row_idx, column=c).value
                  for c in range(1, 35)]
        normalizzati = [(str(v).strip().upper() if v is not None else '')
                        for v in valori]
        if 'NOME' in normalizzati and 'COGNOME' in normalizzati:
            return row_idx, normalizzati
    return None, None


def trasforma(input_path, output_path, sheet_richiesto=None):
    wb = load_workbook(filename=input_path, data_only=True, read_only=True)
    sheet = _scegli_sheet(wb, sheet_richiesto)
    sys.stderr.write(f"Lettura sheet: {sheet.title}\n")

    riga_h, header = _trova_riga_intestazione(sheet)
    if not header:
        sys.stderr.write("ERRORE: riga intestazione NOME/COGNOME "
                         "non trovata nei primi 5 record\n")
        sys.exit(1)
    sys.stderr.write(f"Intestazione trovata a riga {riga_h}\n")

    # Mappa nome colonna -> indice (0-based)
    colonne = {nome: i for i, nome in enumerate(header) if nome}

    def col(row_values, nome):
        idx = colonne.get(nome)
        if idx is None or idx >= len(row_values):
            return None
        return row_values[idx]

    campi_output = [
        'id',
        'name',
        'company_type',
        'is_company',
        'is_socio',
        'stato_socio',
        'categoria_socio',
        'codice_fiscale',
        'data_nascita',
        'luogo_nascita',
        'street',
        'city',
        'stato_civile',
        'function',
        'phone',
        'email',
        'data_iscrizione',
    ]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    soci_emessi = 0
    soci_saltati = 0

    with open(output_path, 'w', encoding='utf-8', newline='') as fout:
        writer = csv.DictWriter(fout, fieldnames=campi_output)
        writer.writeheader()

        for row in sheet.iter_rows(min_row=riga_h + 1, values_only=True):
            nome_full = _stringa(col(row, 'NOME'))
            cognome_full = _stringa(col(row, 'COGNOME'))
            if not (nome_full or cognome_full):
                continue  # riga vuota

            name = (nome_full + ' ' + cognome_full).strip()
            cf = _codice_fiscale(col(row, 'CODICE FISCALE'))

            if not cf:
                sys.stderr.write(
                    f"  WARN: CF mancante per '{name}', salto\n")
                soci_saltati += 1
                continue

            record = {
                'id': f"crocevia_tesseramento.socio_{cf}",
                'name': name,
                'company_type': 'person',
                'is_company': 'False',
                'is_socio': 'True',
                'stato_socio': 'attivo',
                'categoria_socio': _categoria_socio(col(row, 'RUOLO')),
                'codice_fiscale': cf,
                'data_nascita': _parse_data(col(row, 'DATA DI NASCITA')),
                'luogo_nascita': _stringa(col(row, 'LUOGO DI NASCITA')),
                'street': _stringa(col(row, 'INDIRIZZO')),
                'city': _stringa(col(row, 'CITTÀ')),
                'stato_civile': _stato_civile(col(row, 'STATO CIVILE')),
                'function': _stringa(col(row, 'PROFESSIONE')),
                'phone': _telefono(col(row, 'TELEFONO')),
                'email': _email(col(row, 'E-MAIL')),
                'data_iscrizione': _parse_data(col(row, 'DATA')),
            }
            writer.writerow(record)
            soci_emessi += 1

    sys.stderr.write(
        f"\nFatto:\n"
        f"  - {soci_emessi} soci nel CSV di output\n"
        f"  - {soci_saltati} soci saltati (CF mancante)\n"
        f"  - output: {output_path}\n\n"
        f"Prossimo passo:\n"
        f"  Apri Odoo > Tesseramento > Soci > tre puntini > Importa\n"
        f"  records, carica il CSV. Dopo l'import, ELIMINA il CSV dal\n"
        f"  tuo PC (contiene dati personali).\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--input', required=True,
                        help='Percorso al file .xlsx del registro soci')
    parser.add_argument('--output', required=True,
                        help='Percorso del CSV di output')
    parser.add_argument('--sheet', default=None,
                        help="Nome del sheet (default: l'ultimo)")
    args = parser.parse_args()
    trasforma(args.input, args.output, args.sheet)


if __name__ == '__main__':
    main()
