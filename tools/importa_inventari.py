#!/usr/bin/env python3
"""
Converte i Google Sheets di inventario (Barletta + Trani) in un CSV
pronto per Import Records di Odoo (modello crocevia.bene).

USO (gira sul TUO PC, non in repo):

    # scarica i due fogli condivisi come CSV
    curl -sL -o /tmp/inv_barletta.csv \\
        "https://docs.google.com/spreadsheets/d/1tZppwz2MvnN2PDLi2XSsvGolPN-ZAv3MyHADqkiuz7Q/export?format=csv"
    curl -sL -o /tmp/inv_trani.csv \\
        "https://docs.google.com/spreadsheets/d/1xF4q8BZvAdc6ESXjZeayulBQDb-J-2cL4gnijRZJumI/export?format=csv"

    # converti
    python3 tools/importa_inventari.py \\
        --barletta /tmp/inv_barletta.csv \\
        --trani    /tmp/inv_trani.csv \\
        --output   /tmp/inventario_per_odoo.csv

Poi: Odoo > Inventario > Beni > tre puntini > Importa records >
carica /tmp/inventario_per_odoo.csv.

DOPO L'IMPORT:
    rm /tmp/inv_barletta.csv /tmp/inv_trani.csv /tmp/inventario_per_odoo.csv

Note tecniche:
    - Le righe con DIVISORIO=TRUE (separatori visivi nel foglio) e quelle
      senza titolo sono scartate automaticamente.
    - Il campo PROPRIETARIƏ viene mappato a `proprietario_id/.id`
      (partner_id Odoo numerico) per i direttivi conosciuti, altrimenti
      finisce nel campo testo `proprietario_libero`.
    - I partner_id dei direttivi sono cablati nello script: aggiorna
      `PARTNER_BY_NAME` se cambiano.
"""
import argparse
import csv
import re
import sys


# Mappa testo PROPRIETARIƏ (lowercased, trimmed, ? finale rimosso) →
# partner_id Odoo numerico. Per i casi non in mappa il valore va in
# `proprietario_libero` come testo libero.
PARTNER_BY_NAME = {
    'nino tarantino': 8,
    'eleonora': 9,
    'eleonora ghizzota': 9,
    'fabrizio zingrillo': 10,
    'fabrizio': 10,
    'lele': 7,
    'lele damato': 7,
    'giuseppe damato': 7,
}

# Valori liberi normalizzati (per uniformare nomi varianti)
PROP_LIBERO_NORMALIZE = {
    'associazione': 'Crocevia dei Mondi APS',
    'crocevia': 'Crocevia dei Mondi APS',
    'crocevia dei mondi': 'Crocevia dei Mondi APS',
    'crocevia dei mondi aps': 'Crocevia dei Mondi APS',
    'gruppone': 'Gruppone',
    '???': '',
    '?': '',
}


def normalizza_testo(s):
    """Trim + collassa whitespace + rimuove tab/newline interni."""
    if not s:
        return ''
    s = s.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def parse_anno(s):
    """Estrae il primo anno a 4 cifre dalla cella EDIZIONE."""
    if not s:
        return ''
    m = re.search(r'\b(19|20)\d{2}\b', s)
    return m.group(0) if m else ''


def parse_placeholder(s):
    """Vuota i placeholder noti (//, ???, ?, n.d., n/a)."""
    s = normalizza_testo(s)
    if s.lower() in ('//', '/', '???', '??', '?', 'n.d.', 'n/a', 'na', '-'):
        return ''
    return s


parse_autore = parse_placeholder
parse_editore = parse_placeholder


def riga_da_scartare(row):
    """True se la riga e' un divisorio o non ha titolo."""
    if (row.get('DIVISORIO') or '').strip().upper() == 'TRUE':
        return True, 'divisorio'
    if not normalizza_testo(row.get('GIOCO', '')):
        return True, 'vuoto'
    return False, None


def converti_proprietario(prop_raw):
    """Ritorna (partner_id_numerico_o_None, testo_libero)."""
    s = normalizza_testo(prop_raw)
    if not s:
        return (None, '')
    key = s.lower().rstrip(' ?')
    if key in PARTNER_BY_NAME:
        return (PARTNER_BY_NAME[key], '')
    if key in PROP_LIBERO_NORMALIZE:
        return (None, PROP_LIBERO_NORMALIZE[key])
    return (None, s)


def converti_riga(row, sede_xid, idx):
    titolo = normalizza_testo(row.get('GIOCO', ''))
    autore = parse_autore(row.get('AUTORƏ + ILLUSTRATORƏ', ''))
    editore = parse_editore(row.get('EDITORE', ''))
    anno = parse_anno(row.get('EDIZIONE', ''))
    partner_id, libero = converti_proprietario(row.get('PROPRIETARIƏ', ''))

    note_parts = []
    note_csv = normalizza_testo(row.get('NOTE', ''))
    if note_csv:
        note_parts.append(note_csv)
    edizione_raw = normalizza_testo(row.get('EDIZIONE', ''))
    if edizione_raw and not anno:
        note_parts.append(f"Edizione: {edizione_raw}")
    n_copie = normalizza_testo(row.get('N. COPIE', ''))
    try:
        if n_copie and int(n_copie) > 1:
            note_parts.append(f"Copie disponibili: {n_copie}")
    except ValueError:
        pass
    if (row.get('INVENTARIATO') or '').strip().upper() == 'TRUE':
        note_parts.append("Inventariato fisicamente: SI")

    sede_slug = sede_xid.split('.')[1]
    return {
        'id': f"__import__.bene_{sede_slug}_{idx:04d}",
        'name': titolo,
        'categoria': 'gioco_da_tavolo',
        'sede_id/id': sede_xid,
        'autore': autore,
        'editore': editore,
        'anno_pubblicazione': anno,
        'proprietario_id/.id': str(partner_id) if partner_id else '',
        'proprietario_libero': libero,
        'note': ' | '.join(note_parts),
    }


def converti_file(csv_path, sede_xid, out_rows, skipped):
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        idx = 0
        for row in reader:
            scartare, motivo = riga_da_scartare(row)
            if scartare:
                skipped[motivo] = skipped.get(motivo, 0) + 1
                continue
            idx += 1
            out_rows.append(converti_riga(row, sede_xid, idx))
    return idx


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('--barletta', required=True, help='CSV scaricato dal foglio Barletta')
    p.add_argument('--trani', required=True, help='CSV scaricato dal foglio Trani')
    p.add_argument('--output', required=True, help='CSV unico per Odoo')
    args = p.parse_args()

    out_rows = []
    skipped = {}
    n_btl = converti_file(args.barletta, 'crocevia_inventario.sede_barletta', out_rows, skipped)
    n_tra = converti_file(args.trani, 'crocevia_inventario.sede_trani', out_rows, skipped)

    fieldnames = [
        'id', 'name', 'categoria', 'sede_id/id',
        'autore', 'editore', 'anno_pubblicazione',
        'proprietario_id/.id', 'proprietario_libero', 'note',
    ]
    with open(args.output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"OK: scritte {len(out_rows)} righe in {args.output}")
    print(f"    Barletta: {n_btl} beni")
    print(f"    Trani:    {n_tra} beni")
    print(f"    Saltate:  {skipped.get('divisorio', 0)} divisorio + {skipped.get('vuoto', 0)} righe vuote")
    print()
    print("Prossimo passo:")
    print("  Odoo > Inventario > Beni > tre puntini > Importa records")
    print(f"  Carica: {args.output}")
    print("  Dopo l'import: rm i CSV temporanei.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
