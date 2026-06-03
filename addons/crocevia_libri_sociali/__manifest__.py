{
    'name': "Crocevia dei Mondi - Vidimazione libri sociali",
    'version': '18.0.1.0.0',
    'summary': "Vidimazione periodica (firma + marca temporale) del libro soci "
               "e dei libri dei verbali (art. 2215-bis cc)",
    'description': """
Applica ai **libri sociali obbligatori** (art. 15 D.Lgs 117/2017) la stessa
inalterabilita' del registro volontari: una **vidimazione periodica** con
snapshot PDF deterministico, firma elettronica + marca temporale verificate
crittograficamente (pyHanko).

Libri coperti:
- **Libro soci** (res.partner is_socio)
- **Libro verbali assemblee** (crocevia.verbale tipo assemblea_soci)
- **Libro verbali direttivo** (crocevia.verbale tipo riunione_direttivo)

Le note di riunione informali (resoconto_informale) NON fanno parte dei libri
e non vengono vidimate.

Modello a "snapshot periodico firmato": i record restano modificabili, la
vidimazione e' la fotografia firmata del libro a una certa data. Riusa il
verificatore PAdES di crocevia_registro_volontari.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'crocevia_tesseramento',
        'crocevia_navigazione',
        'crocevia_registro_volontari',
        'crocevia_ruoli',
    ],
    'external_dependencies': {
        'python': ['weasyprint', 'pyhanko', 'pyhanko_certvalidator'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'report/report_libri.xml',
        'views/libro_vidimazione_views.xml',
        'views/menu_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
