{
    'name': "Crocevia dei Mondi - Volontariato",
    'version': '18.0.1.1.1',
    'summary': "Libro dei volontari APS + tracciamento ore (art. 17 CTS), light alternativo a hr",
    'description': """
Modulo custom per il libro dei volontari del Crocevia dei Mondi APS.

E' l'alternativa light al modulo `hr` (Dipendenti) di Odoo, che era
overkill per un'associazione: aveva contratti, salari, ferie, skills.
Qui invece teniamo solo cio' che serve per la conformita' APS:

- art. 17 D.Lgs 117/2017 (Codice Terzo Settore): registro volontari
  con nome, cf, data inizio/fine, attivita', polizza assicurativa
- art. 18 CTS: tracciamento ore prestate per rendicontazione bandi,
  copertura INAIL, statistiche per RUNTS

Campi aggiunti a `res.partner`:
- `is_volontario` (boolean, indicizzato) -> filtro per libro volontari
- `data_inizio_volontariato`, `data_fine_volontariato`
- `polizza_volontariato` (estremi polizza di default)
- `attivita_volontariato_descrizione` (mansioni svolte)
- `attivita_volontariato_ids` (O2M con le ore prestate)
- `ore_volontariato_anno_corrente` (computed, somma anno solare)

Nuovo modello `crocevia.attivita.volontariato` (ora prestata):
- volontario (M2O res.partner is_volontario=True)
- data, ore (Float)
- attivita' svolta, note
- polizza al momento (default dalla scheda)
- progetto (M2O project.project, opzionale)
- sede (M2O crocevia.sede, opzionale)

Volontario != socio. Un volontario puo' essere socio (caso comune) o
non socio (es. studente in alternanza, persona che da' una mano in un
evento occasionale). Entrambi vanno nel libro volontari.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'mail',
        'project',
        'crocevia_tesseramento',
        'crocevia_inventario',
        'crocevia_navigazione',
    ],
    'data': [
        'security/crocevia_volontariato_security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/crocevia_attivita_volontariato_views.xml',
        'views/menu_views.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
