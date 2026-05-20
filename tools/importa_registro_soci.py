#!/usr/bin/env python3
"""
Trasforma il registro soci del Crocevia in un CSV pronto per essere
importato in Odoo. Input supportato: file .xlsx (multi-sheet, una per
anno) oppure .csv (single sheet).

USO (gira sul TUO PC, non in repo):

    # da xlsx (sceglie sheet)
    python3 tools/importa_registro_soci.py \\
        --input '/percorso/al/Registro Soci.xlsx' \\
        --output '/tmp/soci_per_odoo.csv' \\
        [--sheet 'Anno 2026']

    # da csv (ignora --sheet, il csv ha un solo "foglio")
    python3 tools/importa_registro_soci.py \\
        --input '/percorso/al/registro_soci_2026.csv' \\
        --output '/tmp/soci_per_odoo.csv'

Per gli xlsx, se non passi `--sheet` prende l'ultimo (di solito l'anno
corrente). Per i csv, il separatore (`,`, `;` o tab) e l'encoding
(UTF-8, UTF-8 BOM, CP1252, ISO-8859-1) vengono detectati automaticamente.

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

DIPENDENZE:
    pip install openpyxl   # solo se l'input e' .xlsx; .csv e' nativo Python

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
       External Identifiers a `__import__.socio_<CF>` (il prefisso
       `__import__` e' quello convenzionale di Odoo per record importati
       via UI: non e' un modulo reale, quindi un upgrade non li
       cancellera')
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

# openpyxl serve solo per .xlsx. L'import e' lazy per non rompere chi usa
# solo input .csv senza averla installata.
try:
    from openpyxl import load_workbook as _load_workbook
    _OPENPYXL_OK = True
except ImportError:
    _load_workbook = None
    _OPENPYXL_OK = False


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


def _trova_intestazione_in_righe(righe):
    """Cerca la riga con NOME e COGNOME nelle prime 5 righe della
    sequenza data. `righe` deve essere indicizzabile.

    Restituisce (riga_idx_1based, header_normalizzato) oppure (None, None).
    """
    for i in range(min(5, len(righe))):
        normalizzati = [
            (str(v).strip().upper() if v is not None else '')
            for v in righe[i]
        ]
        if 'NOME' in normalizzati and 'COGNOME' in normalizzati:
            return i + 1, normalizzati
    return None, None


def _apri_xlsx(input_path, sheet_richiesto):
    """Apre un .xlsx e ritorna (riga_h, header, righe_dati_iter)."""
    if not _OPENPYXL_OK:
        sys.stderr.write(
            "Per leggere .xlsx serve openpyxl. Installalo con:\n"
            "    pip install openpyxl\n"
        )
        sys.exit(1)
    wb = _load_workbook(filename=input_path, data_only=True, read_only=True)
    sheet = _scegli_sheet(wb, sheet_richiesto)
    sys.stderr.write(f"Lettura sheet: {sheet.title}\n")
    # Materializza prime 5 righe per individuare l'intestazione
    prime_righe = []
    for r_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        prime_righe.append(list(row))
        if r_idx >= 5:
            break
    riga_h, header = _trova_intestazione_in_righe(prime_righe)
    if not header:
        sys.stderr.write("ERRORE: riga intestazione NOME/COGNOME "
                         "non trovata nei primi 5 record\n")
        sys.exit(1)
    sys.stderr.write(f"Intestazione trovata a riga {riga_h}\n")
    righe_dati = sheet.iter_rows(min_row=riga_h + 1, values_only=True)
    return riga_h, header, righe_dati


def _apri_csv(input_path, sheet_richiesto):
    """Apre un .csv con autodetect di encoding e separatore.
    Ritorna (riga_h, header, righe_dati_iter)."""
    if sheet_richiesto:
        sys.stderr.write(
            "WARN: --sheet ignorato per input CSV (il csv ha un solo "
            "'foglio')\n"
        )
    encodings = ('utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1')
    last_err = None
    for enc in encodings:
        try:
            with open(input_path, 'r', encoding=enc, newline='') as f:
                campione = f.read(8192)
            # Trovato l'encoding giusto, rileggi tutto.
            try:
                dialect = csv.Sniffer().sniff(campione, delimiters=',;\t|')
            except csv.Error:
                dialect = csv.excel
            with open(input_path, 'r', encoding=enc, newline='') as f:
                rows = list(csv.reader(f, dialect=dialect))
            sys.stderr.write(
                f"Letto CSV: encoding={enc}, separatore="
                f"{dialect.delimiter!r}, {len(rows)} righe\n"
            )
            break
        except UnicodeDecodeError as e:
            last_err = e
            continue
    else:
        sys.stderr.write(
            f"ERRORE: impossibile leggere {input_path} (encoding non "
            f"riconosciuto, ultimo errore: {last_err})\n"
        )
        sys.exit(1)

    riga_h, header = _trova_intestazione_in_righe(rows)
    if not header:
        sys.stderr.write("ERRORE: riga intestazione NOME/COGNOME "
                         "non trovata nei primi 5 record\n")
        sys.exit(1)
    sys.stderr.write(f"Intestazione trovata a riga {riga_h}\n")
    righe_dati = iter(rows[riga_h:])
    return riga_h, header, righe_dati


def trasforma(input_path, output_path, sheet_richiesto=None):
    ext = Path(input_path).suffix.lower()
    if ext in ('.xlsx', '.xlsm'):
        riga_h, header, righe_dati = _apri_xlsx(input_path, sheet_richiesto)
    elif ext == '.csv':
        riga_h, header, righe_dati = _apri_csv(input_path, sheet_richiesto)
    else:
        sys.stderr.write(
            f"ERRORE: estensione '{ext}' non supportata. "
            f"Usa .xlsx, .xlsm o .csv\n"
        )
        sys.exit(1)

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

        for row in righe_dati:
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
                'id': f"__import__.socio_{cf}",
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
