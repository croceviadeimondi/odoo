{
    'name': "Crocevia dei Mondi - Assemblee",
    'version': '18.0.1.0.0',
    'summary': "Sondaggi per scegliere data assemblea + vista Resoconti",
    'description': """
Estende il blocco "Atti" rinominandolo in "Assemblee" e aggiungendoci
due sotto-funzioni:

- **Resoconti**: vista filtrata su `crocevia.verbale` dove `tipo =
  resoconto_informale`. I verbali ufficiali (firma su PDF) restano
  nella voce esistente "Verbali".

- **Sondaggi**: un sondaggio per scegliere la data della prossima
  riunione. Il direttivo propone N date, i soci votano la loro
  preferita. Alla scadenza (default `data_inizio + 4 giorni`) un cron
  chiude il sondaggio, calcola la data vincente e:

      stato attuale - **mock**:
      - log della chiusura nel chatter del sondaggio
      - flag `email_inviata` settato (ma niente email reale)
      - flag `telegram_aggiornato` settato (ma niente call a Telegram)

      stato futuro (quando configureremo bot Telegram + SMTP):
      - poll Telegram nel canale soci, chiusura via API
      - email a tutti i soci attivi col risultato

Cosi' il modello dati e il flusso di voto interno sono gia' usabili da
adesso, mentre l'integrazione esterna si aggancia dopo senza
ridisegnare nulla.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'crocevia_tesseramento',
        'crocevia_navigazione',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/crocevia_sondaggio_views.xml',
        'views/crocevia_resoconto_action.xml',
        'views/menu_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
