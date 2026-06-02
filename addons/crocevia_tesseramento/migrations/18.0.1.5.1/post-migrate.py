"""
Aggiorna il nome it_IT del menu/azione "Soci" -> "Libro soci". Il campo
`name` jsonb tradotto era rimasto a "Soci" in it_IT (l'-u aggiorna solo
la lingua sorgente), quindi va forzato per i DB gia' esistenti.
"""
from odoo import api, SUPERUSER_ID

NOMI = {
    'crocevia_tesseramento.menu_crocevia_soci': "Libro soci",
}
NOMI_AZIONI = {
    'crocevia_tesseramento.action_soci': "Libro soci",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, nome in {**NOMI, **NOMI_AZIONI}.items():
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            rec.with_context(lang='it_IT').write({'name': nome})
