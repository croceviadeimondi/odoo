{
    'name': "Crocevia dei Mondi - Miniapp Telegram",
    'version': '18.0.1.3.0',
    'summary': "Collegamento soci-Telegram e API per la miniapp inventario e prestiti",
    'description': """
Backend Odoo della sezione Inventario della miniapp Telegram.

Funzionalita:
- Campo `telegram_id` sulla scheda socio, univoco, piu' la data in cui il
  socio ha accettato l'informativa dalla miniapp.
- Utente tecnico **Miniapp** (senza password: si usa con una chiave API)
  con il solo gruppo omonimo: legge e scrive beni e prestiti, crea e
  aggiorna schede contatto, legge le sedi. Niente cassa, verbali, registri.
- Modello astratto `crocevia.miniapp` con i metodi chiamati via XML-RPC dal
  server della miniapp: registrazione dei soci, catalogo, prestiti,
  restituzioni, prolungamenti, scaduti, aggiunta beni.

Le regole (un prestito aperto per socio, 30 giorni) stanno qui e non nel
server della miniapp, cosi' valgono qualunque cosa ci sia davanti.
Da Odoo lo staff resta libero di fare eccezioni.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'crocevia_tesseramento',
        'crocevia_inventario',
    ],
    'data': [
        'security/crocevia_miniapp_security.xml',
        'security/ir.model.access.csv',
        'data/parametri_default.xml',
        'data/informativa_miniapp.xml',
        'views/res_partner_views.xml',
    ],
    'application': False,
    'installable': True,
}
