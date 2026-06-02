{
    'name': "Crocevia dei Mondi - Riorganizzazione menu",
    'version': '18.0.2.2.0',
    'summary': "Raggruppa i menu di Odoo per funzione: Soci, Cassa, Atti, Volontariato",
    'description': """
Modulo di sola configurazione: ridisegna la barra app di Odoo
raggruppando i menu per funzione, cosi' anche un utente non avvezzo a
Odoo trova le voci dove le aspetta.

Nuovi menu root creati da questo modulo:
- **Soci** -> Soci, Richieste iscrizione, Cariche direttive, Tutti i
  contatti (ex menu Contatti spostato qui dentro)
- **Cassa** -> Ricevute, Note spese, Fatturazione (sub-menu dell'app
  Account)
- **Atti** -> Verbali
- **Volontariato** -> Volontari (hr), Fogli ore (hr_timesheet),
  Presenze (hr_attendance, se installato)

Menu esistenti riorganizzati:
- **Inventario** (gia' root di crocevia_inventario) -> sequence
  riassegnata per stare dopo Cassa
- **Progetti** -> ospita anche "Da fare" come sotto-voce
- Menu root tematici nativi (hr, hr_expense, hr_timesheet, account,
  contacts, project_todo) vengono riparentati sotto i nuovi root,
  quindi spariscono dalla home Apps come tile separate

Vecchio menu root "Tesseramento" disattivato: le sue voci migrano
sotto Soci / Cassa / Atti.

Disinstallando questo modulo i menu tornano alla loro posizione
originale (Odoo memorizza solo l'override mentre il modulo e' attivo).
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'account',
        'calendar',
        'project',
        'project_todo',
        'spreadsheet_dashboard',
        'crocevia_tesseramento',
        'crocevia_inventario',
    ],
    'data': [
        'data/menu_riorganizzazione.xml',
    ],
    'post_init_hook': 'applica_lessico_navigazione',
    'application': False,
    'installable': True,
    'auto_install': False,
}
