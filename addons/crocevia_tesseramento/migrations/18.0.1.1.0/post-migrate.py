"""
Migration 18.0.1.0.0 -> 18.0.1.1.0

Rinomina del tipo ricevuta `quota_annuale` in `tesseramento` (e della
chiave del parametro di sistema con l'importo di default).

- Aggiorna eventuali ricevute esistenti con il vecchio valore del
  selection (idempotente: nessun effetto se non ce ne sono).
- Rimuove la vecchia entry `ir.config_parameter` con la chiave vecchia,
  e il relativo record `ir.model.data`. Il nuovo parametro viene
  ricreato dal data XML aggiornato (`data/parametri_default.xml`).
"""


def migrate(cr, version):
    if not version:
        return

    # 1. Ricevute esistenti: rinomina il tipo.
    cr.execute("""
        UPDATE crocevia_ricevuta
        SET tipo = 'tesseramento'
        WHERE tipo = 'quota_annuale'
    """)

    # 2. Parametro di sistema: rimuovi il vecchio (il nuovo viene
    #    creato dal load del data XML al termine dell'upgrade).
    cr.execute("""
        DELETE FROM ir_config_parameter
        WHERE key = 'crocevia_tesseramento.importo_quota_annuale'
    """)

    # 3. Record ir.model.data della vecchia entry (per evitare warning
    #    di "external id orphan" alla prossima passata).
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'crocevia_tesseramento'
          AND name = 'param_importo_quota_annuale'
    """)
