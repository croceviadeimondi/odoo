"""
Forza i nomi it_IT dei menu del registro volontari (campo `name` jsonb
senza chiave it_IT -> vuoto in UI italiana in Odoo 18). Gira all'-u con
il bump a 18.0.1.2.0, sistema i DB gia' esistenti.
"""
from odoo import api, SUPERUSER_ID

NOMI_MENU = {
    'crocevia_registro_volontari.menu_registro_volontari_root': "Registro Volontari",
    'crocevia_registro_volontari.menu_registro_iscrizioni': "Iscrizioni",
    'crocevia_registro_volontari.menu_registro_vidimazioni': "Vidimazioni",
    'crocevia_registro_volontari.menu_registro_annullamenti': "Annullamenti",
    'crocevia_registro_volontari.menu_registro_export': "Esporta per assicurazione",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, nome in NOMI_MENU.items():
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.with_context(lang='it_IT').write({'name': nome})
