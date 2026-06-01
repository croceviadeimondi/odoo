"""
Post-init hook che applica le piccole correzioni di traduzione IT che
non si possono fare via data XML (perche' Odoo aggiorna `name` solo in
lingua sorgente quando carichi un `<record>` di update).

Per ora una sola: il sotto-menu "Contatti" (originario del modulo
`contacts`) dentro il nuovo root "Soci" lo rinominiamo in "Tutti i
contatti" per distinguerlo dalla voce "Soci" (che e' filtrato per
`is_socio=True`).
"""

import logging

_logger = logging.getLogger(__name__)


def applica_lessico_navigazione(env):
    menu_contacts = env.ref('contacts.menu_contacts', raise_if_not_found=False)
    if menu_contacts:
        menu_contacts.with_context(lang='it_IT').write({
            'name': 'Tutti i contatti',
        })
        _logger.info(
            "crocevia_navigazione: rinominato menu 'Contatti' in "
            "'Tutti i contatti' (it_IT)."
        )
    # menu_atti_root e' stato creato come "Atti", lo rinominiamo in
    # "Assemblee" (it_IT) cosi' i db gia' migrati si aggiornano senza
    # bisogno di reinstall del modulo.
    menu_atti = env.ref('crocevia_navigazione.menu_atti_root',
                        raise_if_not_found=False)
    if menu_atti:
        menu_atti.with_context(lang='it_IT').write({'name': 'Assemblee'})
        _logger.info(
            "crocevia_navigazione: rinominato menu 'Atti' in 'Assemblee'."
        )
