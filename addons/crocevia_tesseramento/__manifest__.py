{
    'name': "Crocevia dei Mondi — Tesseramento",
    'version': '18.0.1.0.0',
    'summary': "Gestione tesseramento, cariche direttive e verbali per APS/ETS",
    'description': """
Modulo custom per l'associazione di promozione sociale Crocevia dei Mondi.

Funzionalità:
- Registro soci con numero progressivo, categoria (Amministrativo / Volontario
  / Onorario / Direttivo) e stato (richiesta / attivo / cessato)
- Cariche direttive (Presidente, Vicepresidente, Segretario, Tesoriere) con
  date di mandato e storico delle gestioni
- Form pubblico di iscrizione sul sito → richiesta in Odoo da approvare
- Archivio minimo dei verbali (assemblee soci e riunioni del direttivo)
- Esenzione automatica della quota associativa per i soci onorari
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://github.com/croceviadeimondi",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'mail',
        'membership',
        'account',
        'website',
    ],
    'data': [
        'security/crocevia_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/res_partner_views.xml',
        'views/crocevia_carica_views.xml',
        'views/crocevia_richiesta_views.xml',
        'views/crocevia_verbale_views.xml',
        'views/menu_views.xml',
        'views/website_iscrizione_templates.xml',
    ],
    'application': True,
    'installable': True,
}
