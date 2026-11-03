# Da dare in pasto a `odoo shell`, una volta sola (fatto il 3 novembre 2026).
#
# Gli external id dei libri erano legati alla posizione nel foglio
# (`__import__.bene_lib_<sede>_<NNNN>`): inserire una riga spostava tutti
# quelli dopo, e reimportando si aggiornavano i libri sbagliati. Ora
# `tools/importa_inventari.py` ricava l'id dal contenuto (sede, titolo,
# autore, numero). Questo script da' lo stesso id ai libri gia' in Odoo,
# compresi quelli aggiunti a mano o dalla miniapp, cosi' il prossimo import
# li riconosce invece di duplicarli.
#
# USO (sul VPS):
#   docker exec -i crocevia-odoo sh -c "odoo shell -d crocevia --no-http \
#     --db_host=\$HOST --db_user=\$USER --db_password=\$PASSWORD \
#     --db_port=5432 --shell-interface=python" < tools/migra_id_libreria.py
#
# Con SALVA = False fa solo la prova: stampa cosa farebbe e annulla.
import hashlib
import re
import unicodedata

SALVA = False


def normalizza_testo(s):
    # In Odoo un campo vuoto vale False, non '': senza questo diventava "false".
    s = str(s) if s else ''
    s = s.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def norm_chiave(s):
    # Uguale a quella di tools/importa_inventari.py.
    s = unicodedata.normalize('NFKD', normalizza_testo(s).lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def id_libro(sede_slug, titolo, autore, numero, copia):
    # "1.0" e "1" sono lo stesso numero: Excel legge le celle numeriche come
    # decimali, e il vecchio import li aveva salvati cosi'.
    numero = re.sub(r'^(\d+)\.0$', r'\1', normalizza_testo(numero))
    chiave = '|'.join(norm_chiave(x) for x in (titolo, autore, numero))
    h = hashlib.sha1(chiave.encode('utf-8')).hexdigest()[:10]
    return f"libro_{sede_slug}_{h}" + (f"_{copia}" if copia > 1 else '')


Dati = env['ir.model.data']
libri = env['crocevia.bene'].with_context(active_test=False).search(
    [('categoria', '=', 'libro')], order='id')
copie = {}
nuovi_id, tolti = 0, 0
for b in libri:
    sede = Dati.search([('model', '=', 'crocevia.sede'), ('res_id', '=', b.sede_id.id)], limit=1)
    sede_slug = sede.name  # sede_barletta, sede_trani
    m = re.search(r'Numero: ([^|]*)', b.note or '')
    numero = re.sub(r'^(\d+)\.0$', r'\1', m.group(1).strip()) if m else ''
    k = (sede_slug, norm_chiave(b.name), norm_chiave(b.autore), norm_chiave(numero))
    copie[k] = copie.get(k, 0) + 1
    nome = id_libro(sede_slug, b.name, b.autore, numero, copie[k])
    vecchi = Dati.search([('module', '=', '__import__'), ('model', '=', 'crocevia.bene'),
                          ('res_id', '=', b.id)])
    tolti += len(vecchi.filtered(lambda d: d.name != nome))
    vecchi.filtered(lambda d: d.name != nome).unlink()
    if not Dati.search_count([('module', '=', '__import__'), ('name', '=', nome)]):
        Dati.create({'module': '__import__', 'name': nome, 'model': 'crocevia.bene',
                     'res_id': b.id, 'noupdate': False})
        nuovi_id += 1

doppie = {k: n for k, n in copie.items() if n > 1}
print('RISULTATO libri', len(libri), '| id nuovi', nuovi_id, '| id vecchi tolti', tolti,
      '| chiavi con piu copie', len(doppie))
if SALVA:
    env.cr.commit()
    print('RISULTATO salvato')
else:
    env.cr.rollback()
    print('RISULTATO prova: annullato')
