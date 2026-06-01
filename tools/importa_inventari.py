#!/usr/bin/env python3
"""
Converte i Google Sheets di inventario (Barletta + Trani) in un CSV
pronto per Import Records di Odoo (modello crocevia.bene).

Ogni workbook ha piu' fogli: ne importiamo QUATTRO, ciascuno con uno
schema di colonne diverso:
  - GDT           -> categoria gioco_da_tavolo
  - GDR           -> categoria gioco_di_ruolo
  - Attrezzature  -> categoria altro
  - Oggettistica  -> categoria altro
I fogli "Wishlist GDT", "Wishlist GDR", "Vecchio GDT", "Vecchio GDR"
sono IGNORATI di proposito.

USO (gira sul TUO PC, non in repo; richiede openpyxl):

    # scarica i DUE workbook INTERI (tutti i fogli) come xlsx.
    # NB: format=csv esporterebbe solo il primo foglio -> usare xlsx.
    curl -sL -o /tmp/wb_barletta.xlsx \\
        "https://docs.google.com/spreadsheets/d/1tZppwz2MvnN2PDLi2XSsvGolPN-ZAv3MyHADqkiuz7Q/export?format=xlsx"
    curl -sL -o /tmp/wb_trani.xlsx \\
        "https://docs.google.com/spreadsheets/d/1xF4q8BZvAdc6ESXjZeayulBQDb-J-2cL4gnijRZJumI/export?format=xlsx"

    # converti
    python3 tools/importa_inventari.py \\
        --barletta /tmp/wb_barletta.xlsx \\
        --trani    /tmp/wb_trani.xlsx \\
        --output   /tmp/inventario_per_odoo.csv

Poi: Odoo > Inventario > Beni > tre puntini > Importa records >
carica /tmp/inventario_per_odoo.csv.

DOPO L'IMPORT:
    rm /tmp/wb_barletta.xlsx /tmp/wb_trani.xlsx /tmp/inventario_per_odoo.csv

Note tecniche:
    - External id deterministici `__import__.bene_<sede>_<NNNN>`, contati
      per sede nell'ordine GDT, GDR, Attrezzature, Oggettistica. I beni
      GDT gia' importati (Barletta 0001..0158, Trani 0001..0046) vengono
      cosi' AGGIORNATI, non duplicati, e gli altri fogli accodati dopo.
    - Le righe senza titolo e i divisori (DIVISORIO=TRUE, solo GDT) sono
      scartate automaticamente.
    - Il campo proprietario viene mappato a `proprietario_id/.id` per i
      direttivi noti (PARTNER_BY_NAME), altrimenti finisce nel testo
      libero `proprietario_libero`. Aggiorna PARTNER_BY_NAME se cambiano.
"""
import argparse
import re
import sys

try:
    import openpyxl
except ImportError:
    sys.exit("ERRORE: serve openpyxl. Installa con: pip install openpyxl")


# Mappa testo proprietario (lowercased, trimmed, ? finale rimosso) ->
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
    """Trim + collassa whitespace + rimuove tab/newline interni.
    Coerce a stringa (le celle xlsx possono essere numeri/bool)."""
    if s is None:
        return ''
    s = str(s)
    s = s.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def parse_anno(s):
    """Estrae il primo anno a 4 cifre dalla cella EDIZIONE."""
    s = normalizza_testo(s)
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


def cella_true(v):
    """True per checkbox xlsx (bool) o stringa 'TRUE'."""
    if isinstance(v, bool):
        return v
    return normalizza_testo(v).upper() == 'TRUE'


def parse_int(v):
    """Ritorna int o None (le celle numeriche xlsx sono float)."""
    s = normalizza_testo(v)
    if not s:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


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


def _nota_copie(row, col, label="Copie disponibili"):
    n = parse_int(row.get(col, ''))
    return f"{label}: {n}" if n and n > 1 else None


# ---------------------------------------------------------------------
# Builder per foglio. Ognuno riceve la riga (dict header->valore) e
# ritorna il dict dei campi bene, oppure None se la riga va scartata.
# ---------------------------------------------------------------------

def build_gdt(row):
    titolo = normalizza_testo(row.get('GIOCO', ''))
    if not titolo or cella_true(row.get('DIVISORIO', '')):
        return None
    anno = parse_anno(row.get('EDIZIONE', ''))
    note = []
    n = parse_placeholder(row.get('NOTE', ''))
    if n:
        note.append(n)
    ediz = normalizza_testo(row.get('EDIZIONE', ''))
    if ediz and not anno:
        note.append(f"Edizione: {ediz}")
    c = _nota_copie(row, 'N. COPIE')
    if c:
        note.append(c)
    if cella_true(row.get('INVENTARIATO', '')):
        note.append("Inventariato fisicamente: SI")
    pid, libero = converti_proprietario(row.get('PROPRIETARIƏ', ''))
    return {
        'name': titolo,
        'categoria': 'gioco_da_tavolo',
        'autore': parse_placeholder(row.get('AUTORƏ + ILLUSTRATORƏ', '')),
        'editore': parse_placeholder(row.get('EDITORE', '')),
        'anno_pubblicazione': anno,
        'proprietario_id/.id': str(pid) if pid else '',
        'proprietario_libero': libero,
        'note': ' | '.join(note),
    }


def build_gdr(row):
    titolo = normalizza_testo(row.get('GIOCO', ''))
    if not titolo:
        return None
    anno = parse_anno(row.get('EDIZIONE', ''))
    note = []
    sistema = normalizza_testo(row.get('SISTEMA', ''))
    if sistema:
        note.append(f"Sistema: {sistema}")
    n = parse_placeholder(row.get('NOTE', ''))
    if n:
        note.append(n)
    ediz = normalizza_testo(row.get('EDIZIONE', ''))
    if ediz and not anno:
        note.append(f"Edizione: {ediz}")
    c = _nota_copie(row, 'N. COPIE')
    if c:
        note.append(c)
    if cella_true(row.get('INVENTARIATO', '')):
        note.append("Inventariato fisicamente: SI")
    pid, libero = converti_proprietario(row.get('PROPRIETARIO', ''))
    return {
        'name': titolo,
        'categoria': 'gioco_di_ruolo',
        'autore': parse_placeholder(row.get('AUTORƏ', '')),
        'editore': parse_placeholder(row.get('EDITORE', '')),
        'anno_pubblicazione': anno,
        'proprietario_id/.id': str(pid) if pid else '',
        'proprietario_libero': libero,
        'note': ' | '.join(note),
    }


def build_attrezzature(row):
    titolo = normalizza_testo(row.get('OGGETTO', ''))
    if not titolo:
        return None
    note = []
    luogo = normalizza_testo(row.get('LUOGO', ''))
    if luogo:
        note.append(f"Luogo: {luogo}")
    # FUNGE? = funziona? Annotiamo solo quando NON funziona.
    funge_raw = normalizza_testo(row.get('FUNGE?', ''))
    if funge_raw and not cella_true(row.get('FUNGE?', '')):
        note.append("Stato: non funzionante")
    c = _nota_copie(row, 'QUANTITÀ', label="Quantita'")
    if c:
        note.append(c)
    n = parse_placeholder(row.get('NOTE', ''))
    if n:
        note.append(n)
    pid, libero = converti_proprietario(row.get('PROPRIETARIO', ''))
    return {
        'name': titolo,
        'categoria': 'altro',
        'autore': '',
        'editore': '',
        'anno_pubblicazione': '',
        'proprietario_id/.id': str(pid) if pid else '',
        'proprietario_libero': libero,
        'note': ' | '.join(note),
    }


def build_oggettistica(row):
    titolo = normalizza_testo(row.get('OGGETTO', ''))
    if not titolo:
        return None
    note = []
    luogo = normalizza_testo(row.get('LUOGO', ''))
    if luogo:
        note.append(f"Luogo: {luogo}")
    c = _nota_copie(row, 'N. COPIE')
    if c:
        note.append(c)
    n = parse_placeholder(row.get('NOTE', ''))
    if n:
        note.append(n)
    pid, libero = converti_proprietario(row.get('PROPRIETARIƏ', ''))
    return {
        'name': titolo,
        'categoria': 'altro',
        'autore': '',
        'editore': '',
        'anno_pubblicazione': '',
        'proprietario_id/.id': str(pid) if pid else '',
        'proprietario_libero': libero,
        'note': ' | '.join(note),
    }


# Ordine FISSO: GDT prima (ids stabili con l'import precedente), poi gli
# altri. (nome_foglio, builder).
FOGLI = [
    ('GDT', build_gdt),
    ('GDR', build_gdr),
    ('Attrezzature', build_attrezzature),
    ('Oggettistica', build_oggettistica),
]


def iter_righe(ws):
    """Yield dict {header: valore} per ogni riga dati del foglio."""
    header = None
    for row in ws.iter_rows(values_only=True):
        if header is None:
            header = [normalizza_testo(c) for c in row]
            continue
        d = {}
        for i, h in enumerate(header):
            if h:
                d[h] = row[i] if i < len(row) else ''
        yield d


def converti_workbook(path, sede_xid, out_rows, stats):
    """Itera i fogli noti del workbook, accoda le righe convertite.
    Numerazione per sede continua tra i fogli (GDT mantiene gli id
    dell'import precedente)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sede_slug = sede_xid.split('.')[1]
    idx = 0
    tot = 0
    for nome_foglio, builder in FOGLI:
        if nome_foglio not in wb.sheetnames:
            stats['fogli_mancanti'].append(f"{sede_slug}:{nome_foglio}")
            continue
        ws = wb[nome_foglio]
        n_foglio = 0
        for row in iter_righe(ws):
            vals = builder(row)
            if vals is None:
                continue
            idx += 1
            n_foglio += 1
            vals['id'] = f"__import__.bene_{sede_slug}_{idx:04d}"
            vals['sede_id/id'] = sede_xid
            out_rows.append(vals)
        stats['per_foglio'].append((sede_slug, nome_foglio, n_foglio))
        tot += n_foglio
    wb.close()
    return tot


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('--barletta', required=True, help='xlsx workbook Barletta')
    p.add_argument('--trani', required=True, help='xlsx workbook Trani')
    p.add_argument('--output', required=True, help='CSV unico per Odoo')
    args = p.parse_args()

    import csv
    out_rows = []
    stats = {'per_foglio': [], 'fogli_mancanti': []}
    n_btl = converti_workbook(
        args.barletta, 'crocevia_inventario.sede_barletta', out_rows, stats)
    n_tra = converti_workbook(
        args.trani, 'crocevia_inventario.sede_trani', out_rows, stats)

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
    print(f"    Barletta: {n_btl} beni  |  Trani: {n_tra} beni")
    print("    Dettaglio per foglio:")
    for sede, foglio, n in stats['per_foglio']:
        print(f"      {sede:18s} {foglio:14s} {n:4d}")
    if stats['fogli_mancanti']:
        print(f"    Fogli attesi non trovati: {', '.join(stats['fogli_mancanti'])}")
    print()
    print("Prossimo passo:")
    print("  Odoo > Inventario > Beni > tre puntini > Importa records")
    print(f"  Carica: {args.output}")
    print("  Dopo l'import: rm i file temporanei.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
