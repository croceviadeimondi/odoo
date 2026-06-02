"""
Forza i nomi it_IT dei menu del modulo. In Odoo 18 il campo `name` jsonb,
senza chiave it_IT esplicita, mostra stringa vuota (niente fallback su
en_US): i menu apparivano vuoti nell'interfaccia italiana. Qui li
valorizziamo per i DB gia' esistenti (gira all'-u con bump di versione).
"""
from odoo import api, SUPERUSER_ID

NOMI_MENU = {
    'crocevia_volontariato.menu_crocevia_libro_volontari': "Libro volontari",
    'crocevia_volontariato.menu_crocevia_ore_volontariato': "Ore prestate",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, nome in NOMI_MENU.items():
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.with_context(lang='it_IT').write({'name': nome})
