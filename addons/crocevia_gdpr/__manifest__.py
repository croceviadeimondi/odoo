{
    'name': "Crocevia dei Mondi - Accettazione GDPR",
    'version': '18.0.1.0.0',
    'summary': "Accettazione obbligatoria dell'informativa privacy al primo accesso",
    'description': """
Al primo accesso al gestionale, ogni utente interno deve accettare
l'informativa privacy/GDPR prima di poter usare l'applicazione.

Come funziona:
- aggiunge `gdpr_accettata` (+ data) su res.users;
- l'accesso al web client (/web, /odoo) e' intercettato lato server: se
  l'utente non ha ancora accettato, viene rediretto a una pagina con
  l'informativa e un bottone "Accetto" (blocco effettivo, non aggirabile);
- il testo dell'informativa e' un parametro di sistema editabile
  (`crocevia_gdpr.informativa_html`), cosi' il direttivo lo aggiorna senza
  toccare il codice.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'data/parametri.xml',
        'views/gdpr_templates.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
