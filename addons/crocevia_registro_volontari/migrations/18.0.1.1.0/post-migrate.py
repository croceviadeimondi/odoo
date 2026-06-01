"""
Migration 18.0.1.0.0 -> 18.0.1.1.0.

Introduce il campo `stato_inalterabilita` su `crocevia.registro.iscrizione`
con valori `bozza` / `vidimato`. I record creati con la v1.0 erano gia'
trattati come write-once dal codice (override di `write`/`unlink`),
quindi devono essere marcati direttamente come `vidimato` per non
perdere la garanzia di inalterabilita' gia' applicata.

I record creati dopo questo upgrade saranno invece in `bozza` di
default, modificabili fino alla prossima vidimazione (modello v1.1).
"""


def migrate(cr, version):
    if not version:
        return
    # Tutti i record esistenti -> 'vidimato' (erano gia' write-once
    # nella v1.0). Hash chain gia' calcolata al momento del create
    # nella v1.0, resta valida.
    cr.execute("""
        UPDATE crocevia_registro_iscrizione
        SET stato_inalterabilita = 'vidimato'
        WHERE stato_inalterabilita IS NULL OR stato_inalterabilita = ''
    """)
