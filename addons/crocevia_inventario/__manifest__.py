{
    'name': "Crocevia dei Mondi - Inventario",
    'version': '18.0.1.2.0',
    'summary': "Inventario di giochi, manuali e libri delle sedi APS, con prestiti",
    'description': """
Modulo custom per l'inventario del Crocevia dei Mondi APS.

Funzionalita:
- Registro delle **sedi** (Barletta, Trani) con citta', indirizzo,
  referente, flag `is_sede_legale`. Le 2 sedi attuali sono pre-popolate
  come dati iniziali (`noupdate=1`).
- Registro dei **beni**: giochi da tavolo, giochi di ruolo, manuali,
  libri, altro. Ciascuno collegato a una sede, con codice interno,
  autore/editore/anno/ISBN, valore stimato, note. Audit via chatter.
- Registro dei **prestiti**: chi ha preso quale bene, da quando, fino
  a quando, stato calcolato (in corso / in ritardo / restituito).
  Vincolo: un bene puo' avere al massimo un prestito attivo.

Pensato per ludoteche/biblioteche di APS, NON per la vendita: niente
agganci con `stock`/`product` di Odoo, niente movimenti di magazzino.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'mail',
    ],
    'data': [
        'security/crocevia_inventario_security.xml',
        'security/ir.model.access.csv',
        'views/crocevia_sede_views.xml',
        'views/crocevia_bene_views.xml',
        'views/crocevia_prestito_views.xml',
        'wizards/crocevia_bene_wizard_views.xml',
        'views/menu_views.xml',
        'data/sedi_iniziali.xml',
    ],
    'application': True,
    'installable': True,
}
