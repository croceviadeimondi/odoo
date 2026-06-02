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

C'e' anche la LIBRERIA: workbook separati (uno per sede), con un foglio
per genere (Romanzi, Fumetti, Manga, Biografie, ...). Tutti i fogli
diventano categoria `libro`, col campo `genere` preso dal nome del
foglio. I prestiti annotati nei fogli vanno in nota (niente dati
personali strutturati).

USO (gira sul TUO PC, non in repo; richiede openpyxl):

    # GIOCHI: scarica i DUE workbook INTERI come xlsx.
    # NB: format=csv esporterebbe solo il primo foglio -> usare xlsx.
    curl -sL -o /tmp/wb_barletta.xlsx \\
        "https://docs.google.com/spreadsheets/d/1tZppwz2MvnN2PDLi2XSsvGolPN-ZAv3MyHADqkiuz7Q/export?format=xlsx"
    curl -sL -o /tmp/wb_trani.xlsx \\
        "https://docs.google.com/spreadsheets/d/1xF4q8BZvAdc6ESXjZeayulBQDb-J-2cL4gnijRZJumI/export?format=xlsx"
    # LIBRERIA: idem (i due file vanno condivisi "chiunque con il link").
    curl -sL -o /tmp/lib_barletta.xlsx \\
        "https://docs.google.com/spreadsheets/d/13_TWMc7MSWzn-S2wYjHqX8fofZgdyr3J/export?format=xlsx"
    curl -sL -o /tmp/lib_trani.xlsx \\
        "https://docs.google.com/spreadsheets/d/1VnKlalJhoPW1avXNnAAehe1XzxDdJ1cH/export?format=xlsx"

    # converti (le sorgenti sono tutte opzionali: indicane almeno una)
    python3 tools/importa_inventari.py \\
        --barletta /tmp/wb_barletta.xlsx --trani /tmp/wb_trani.xlsx \\
        --libreria-barletta /tmp/lib_barletta.xlsx \\
        --libreria-trani    /tmp/lib_trani.xlsx \\
        --output   /tmp/inventario_per_odoo.csv

Poi: Odoo > Inventario > Beni > tre puntini > Importa records >
carica /tmp/inventario_per_odoo.csv.

DOPO L'IMPORT:
    rm /tmp/wb_*.xlsx /tmp/lib_*.xlsx /tmp/inventario_per_odoo.csv

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
    # Il sistema del GdR (D&D, Pathfinder, ...) va nel campo strutturato
    # `genere` (etichettato "Genere / Sistema"), non piu' solo in nota.
    sistema = normalizza_testo(row.get('SISTEMA', ''))
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
    pid, libero = converti_proprietario(row.get('PROPRIETARIO', ''))
    return {
        'name': titolo,
        'categoria': 'gioco_di_ruolo',
        'sistema_id': sistema,
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


# ---------------------------------------------------------------------
# Libreria: workbook separati (uno per sede), un foglio per GENERE.
# Tutti i fogli sono libri/fumetti -> categoria 'libro', col genere preso
# dal nome del foglio. I prestiti vanno in nota (scelta CDM, niente
# match nomi -> niente dati personali strutturati).
# ---------------------------------------------------------------------

GENERE_LIBRERIA = {
    'ROMANZI, SAGGI': 'Romanzi e saggi',
    'Edizioni Per Il Club Del Libro': 'Club del Libro',
    'LIBRI PER BAMBINI, YOUNG ADULT': 'Bambini e Young Adult',
    'FUMETTI DISNEY': 'Fumetti Disney',
    'FUMETTI e GRAPHIC NOVEL': 'Fumetti e Graphic Novel',
    'MANGA, MANHWA': 'Manga e Manhwa',
    'LE GRANDI BIOGRAFIE - FABBRI ED': 'Biografie',
    'COLLANE': 'Collane',
    'VARI': 'Vari',
    'Libri scolasticidi testo': 'Libri scolastici',
    # Fogli specifici di Trani
    'FUMETTI': 'Fumetti e Graphic Novel',
    'Libri sul disegno': 'Libri sul disegno',
    'La mia enciclopedia': 'Enciclopedie',
}


def _col(row, *candidati):
    """Primo valore non vuoto tra header alternativi (match senza spazi,
    case-insensitive) - i fogli libreria hanno intestazioni leggermente
    diverse (AUTORE / AUTRICE vs AUTORE/AUTRICE, ecc.)."""
    chiavi = {c.upper().replace(' ', '') for c in candidati}
    for hk, v in row.items():
        if normalizza_testo(hk).upper().replace(' ', '') in chiavi:
            val = normalizza_testo(v)
            if val:
                return val
    return ''


def build_libro(row, genere):
    titolo = _col(row, 'TITOLO', 'TITOLO / COLLANA')
    if not titolo:
        return None
    mese_anno = _col(row, 'MESE - ANNO')
    anno = parse_anno(mese_anno)
    note = []
    collana = _col(row, 'COLLANA / DETTAGLI / SPECIFICHE', 'DETTAGLI / SPECIFICHE')
    if collana:
        note.append(collana)
    numero = _col(row, 'NUMERO')
    if numero:
        note.append(f"Numero: {numero}")
    if mese_anno and not anno:
        note.append(f"Periodo: {mese_anno}")
    # Prestito -> testo in nota (niente crocevia.prestito, scelta CDM).
    presta = _col(row, 'IN PRESTITO A', 'IN PRESTITO A:')
    data_p = _col(row, 'DATA', 'DATA:').split(' ')[0]  # togli l'ora se data
    if presta:
        note.append(f"In prestito a {presta}" + (f" dal {data_p}" if data_p else ""))
    return {
        'name': titolo,
        'categoria': 'libro',
        'genere_ids': genere,
        'autore': _col(row, 'AUTORE / AUTRICE', 'AUTORE/AUTRICE'),
        'editore': _col(row, 'CASA EDITRICE'),
        'anno_pubblicazione': anno,
        'proprietario_id/.id': '',
        'proprietario_libero': 'Crocevia dei Mondi APS',
        'note': ' | '.join(note),
    }


def converti_workbook_libreria(path, sede_xid, out_rows, stats):
    """Itera TUTTI i fogli del workbook libreria (uno per genere)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sede_slug = sede_xid.split('.')[1]
    idx = 0
    tot = 0
    for nome_foglio in wb.sheetnames:
        genere = GENERE_LIBRERIA.get(nome_foglio, nome_foglio.strip())
        ws = wb[nome_foglio]
        n_foglio = 0
        for row in iter_righe(ws):
            vals = build_libro(row, genere)
            if vals is None:
                continue
            idx += 1
            n_foglio += 1
            # Namespace id distinto dai giochi (bene_<sede>) per non
            # collidere: bene_lib_<sede>.
            vals['id'] = f"__import__.bene_lib_{sede_slug}_{idx:04d}"
            vals['sede_id/id'] = sede_xid
            out_rows.append(vals)
        stats['per_foglio'].append((sede_slug + ' [lib]', genere, n_foglio))
        tot += n_foglio
    wb.close()
    return tot


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
    # Giochi (workbook con fogli GDT/GDR/Attrezzature/Oggettistica).
    p.add_argument('--barletta', help='xlsx workbook GIOCHI Barletta')
    p.add_argument('--trani', help='xlsx workbook GIOCHI Trani')
    # Libreria (workbook con un foglio per genere).
    p.add_argument('--libreria-barletta', dest='lib_barletta',
                   help='xlsx workbook LIBRERIA Barletta')
    p.add_argument('--libreria-trani', dest='lib_trani',
                   help='xlsx workbook LIBRERIA Trani')
    p.add_argument('--output', required=True, help='CSV unico per Odoo')
    args = p.parse_args()

    if not any([args.barletta, args.trani, args.lib_barletta, args.lib_trani]):
        p.error("indica almeno una sorgente (--barletta/--trani e/o "
                "--libreria-barletta/--libreria-trani)")

    import csv
    out_rows = []
    stats = {'per_foglio': [], 'fogli_mancanti': []}
    if args.barletta:
        converti_workbook(args.barletta, 'crocevia_inventario.sede_barletta',
                          out_rows, stats)
    if args.trani:
        converti_workbook(args.trani, 'crocevia_inventario.sede_trani',
                          out_rows, stats)
    if args.lib_barletta:
        converti_workbook_libreria(
            args.lib_barletta, 'crocevia_inventario.sede_barletta', out_rows, stats)
    if args.lib_trani:
        converti_workbook_libreria(
            args.lib_trani, 'crocevia_inventario.sede_trani', out_rows, stats)

    fieldnames = [
        'id', 'name', 'categoria', 'genere_ids', 'sistema_id', 'sede_id/id',
        'autore', 'editore', 'anno_pubblicazione',
        'proprietario_id/.id', 'proprietario_libero', 'note',
    ]
    with open(args.output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval='')
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"OK: scritte {len(out_rows)} righe in {args.output}")
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
