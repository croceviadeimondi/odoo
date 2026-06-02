{
    'name': "Crocevia dei Mondi - Ruolo direttivo unificato",
    'version': '18.0.3.0.0',
    'summary': "Gruppo 'Direttivo del Crocevia' che ingloba i permessi gestionali",
    'description': """
Modulo di configurazione: definisce un singolo gruppo "Direttivo del
Crocevia" che combina (`implied_ids`) i permessi necessari ai membri
del direttivo per gestire l'APS senza dover dipendere da un admin
di sistema esterno.

Gruppi inglobati:
- `base.group_system` (Settings) - gestione utenti, parametri, moduli
- `base.group_partner_manager` (Contact Creation) - creazione contatti
- `account.group_account_manager` (Accounting Administrator) - fatture,
  giornali, conti, riconciliazione
- `hr.group_hr_manager` (HR Administrator) - gestione volontari
- `hr_expense.group_hr_expense_manager` (Expenses Administrator) -
  gestione e approvazione note spese
- `crocevia_tesseramento.group_crocevia_direttivo` - soci, cariche,
  richieste, verbali del modulo tesseramento
- `crocevia_inventario.group_crocevia_inventario` - sedi, beni, prestiti

In pratica: chi e' nel gruppo "Direttivo del Crocevia" puo' fare la
maggior parte delle cose fattibili da un admin Odoo, limitatamente a
cosa serve all'APS.

Installazione: dopo aver installato gli altri moduli aps richiesti
nelle dipendenze, installare `crocevia_ruoli` e poi spuntare il
gruppo "Direttivo del Crocevia" sui membri del direttivo da
Impostazioni > Utenti > Diritti d'accesso > Crocevia dei Mondi.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'mail',
        'account',
        'project',
        'project_todo',
        'crocevia_tesseramento',
        'crocevia_inventario',
        'crocevia_volontariato',
        'crocevia_navigazione',
    ],
    'data': [
        'security/crocevia_ruoli_security.xml',
        'security/ir.model.access.csv',
        'data/menu_visibilita.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
