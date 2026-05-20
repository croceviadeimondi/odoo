{
    'name': "Crocevia dei Mondi - Lessico Volontariato",
    'version': '18.0.1.0.0',
    'summary': "Rinomina 'Dipendente/i' in 'Volontario/i' nei moduli HR",
    'description': """
Modulo di sola configurazione per l'APS Crocevia dei Mondi.

Sostituisce, nella traduzione italiana dei moduli HR di Odoo, i termini:
    'Dipendente'  -> 'Volontario'
    'Dipendenti'  -> 'Volontari'

La sostituzione viene applicata al momento dell'installazione (e a ogni
aggiornamento del modulo con `-u crocevia_hr_lexico`) tramite un
`post_init_hook` Python che riscrive direttamente i campi tradotti
`jsonb` dei record creati dai moduli HR installati:
    - `ir.ui.menu` (voci di menu)
    - `ir.actions.act_window`, `ir.actions.server`, `ir.actions.report`
    - `ir.ui.view` (arch_db)
    - `ir.model` (nome del modello)
    - `ir.model.fields` (label e help dei campi)

In caso di aggiornamento dei moduli `hr*` di Odoo (`-u hr`), Odoo ripristina
le traduzioni originali. Per riapplicare il lessico volontariato eseguire
`-u crocevia_hr_lexico`.
""",
    'author': "Crocevia dei Mondi APS",
    'website': "https://croceviadeimondi.org",
    'category': 'Association',
    'license': 'LGPL-3',
    'depends': ['hr'],
    'data': [],
    'post_init_hook': 'applica_lessico_volontariato',
    'installable': True,
    'auto_install': False,
}
