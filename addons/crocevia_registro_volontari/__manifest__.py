{
    'name': "Crocevia dei Mondi - Registro Volontari",
    'version': '18.0.2.0.0',
    'summary': "Registro volontari ETS conforme DM 6 ottobre 2021: "
               "inalterabilita', hash chain, vidimazione digitale",
    'description': """
Modulo per la tenuta del **registro dei volontari** del Crocevia dei
Mondi APS conforme al DM 6 ottobre 2021 e all'art. 2215-bis del Codice
Civile.

Caratteristiche:
- Write-once: tutti i campi anagrafici sono bloccati dopo la creazione
- Hash chain SHA-256 tra record successivi (tamper-evidence)
- Numerazione progressiva via `ir.sequence`, mai riusata
- Override ORM di `write` e `unlink` (vincoli anche per superuser)
- Workflow di annullamento (no cancellazione) con log motivazione
- Snapshot PDF deterministico (via weasyprint + qpdf normalizzazione)
- Vidimazione: firma + marca temporale RFC 3161 applicate ESTERNAMENTE
  dal responsabile, modulo verifica e archivia
- Reminder cron annuale per la firma del registro
- Export CSV per compagnia assicurativa

Scope di questa iterazione (v1.0):
- Modelli + write-once + hash chain + snapshot PDF + wizard
  annullamento/cessazione/export + cron reminder
- Verifica firma pyHanko: integrazione **mockata** (campo manuale
  "firma valida sì/no" + chatter dei dettagli). Verifica crittografica
  reale aggiunta in v2.0 con bundle CA AgID + trust roots.

Coesistenza con `crocevia_volontariato`:
- `crocevia_volontariato` resta come gestione operativa quotidiana
  (flag is_volontario sul partner, ore prestate, polizza di default)
- `crocevia_registro_volontari` aggiunge sopra il registro **legale**
  write-once. All'iscrizione si snapshotta dal `res.partner`.

Vedi `README.md` del modulo per istruzioni di firma esterna e
aggiornamento trust roots.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'contacts',
        'crocevia_ruoli',
        # Per annidare il menu sotto il root "Volontariato" di navigazione.
        'crocevia_navigazione',
    ],
    'external_dependencies': {
        'python': ['weasyprint', 'pyhanko', 'pyhanko_certvalidator'],
    },
    'data': [
        'security/crocevia_registro_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/parametri.xml',
        'wizards/crocevia_registro_annullamento_wizard_views.xml',
        'wizards/crocevia_registro_cessazione_wizard_views.xml',
        'wizards/crocevia_registro_export_wizard_views.xml',
        'views/crocevia_registro_iscrizione_views.xml',
        'views/crocevia_registro_vidimazione_views.xml',
        'views/crocevia_registro_annullamento_views.xml',
        'report/report_registro_volontari.xml',
        'views/menu_views.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
