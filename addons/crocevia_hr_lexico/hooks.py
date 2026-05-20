"""
Post-init hook che riscrive i termini italiani 'Dipendente/i' -> 'Volontario/i'
nei record creati dai moduli HR di Odoo installati nel DB.

La sostituzione tocca solo la chiave `it_IT` dei campi tradotti jsonb,
preservando le altre lingue (in particolare `en_US`).
"""

import logging

_logger = logging.getLogger(__name__)


# Sostituzioni case-sensitive. Le forme lunghe vanno prima delle corte
# per evitare doppie sostituzioni (es. "Dipendenti" intercettato come
# "Dipendente" + "i").
SOSTITUZIONI = [
    ('Dipendenti', 'Volontari'),
    ('Dipendente', 'Volontario'),
    ('dipendenti', 'volontari'),
    ('dipendente', 'volontario'),
]


# Moduli HR di Odoo sui cui record applichiamo il lessico volontariato.
# La lista include tutti i figli di `hr` che possono essere installati;
# il filtro su `state = installed` esclude quelli effettivamente assenti.
MODULI_HR = (
    'hr',
    'hr_skills',
    'hr_org_chart',
    'mail_bot_hr',
    'hr_timesheet',
    'hr_attendance',
    'hr_recruitment',
    'hr_holidays',
    'hr_contract',
)


def _sostituisci(testo):
    if not testo or not isinstance(testo, str):
        return testo
    nuovo = testo
    for sorgente, target in SOSTITUZIONI:
        nuovo = nuovo.replace(sorgente, target)
    return nuovo


def applica_lessico_volontariato(env):
    """Entry-point del `post_init_hook` dichiarato nel manifest."""

    moduli_installati = env['ir.module.module'].search([
        ('name', 'in', MODULI_HR),
        ('state', '=', 'installed'),
    ]).mapped('name')

    if not moduli_installati:
        _logger.info(
            "crocevia_hr_lexico: nessun modulo HR installato, "
            "niente sostituzioni da applicare."
        )
        return

    _logger.info(
        "crocevia_hr_lexico: applico lessico volontariato per moduli HR "
        "installati: %s", moduli_installati,
    )

    contatori = {}

    # 1) Record con xml_id appartenente ai moduli HR (menu, action, view).
    #    Per ir.ui.view aggiorniamo arch_db (XML delle viste con string="..."
    #    e label che contengono "Dipendente").
    campi_per_model = {
        'ir.ui.menu': ['name'],
        'ir.actions.act_window': ['name'],
        'ir.actions.server': ['name'],
        'ir.actions.report': ['name'],
        'ir.ui.view': ['arch_db'],
    }
    data_records = env['ir.model.data'].search([
        ('module', 'in', moduli_installati),
        ('model', 'in', list(campi_per_model.keys())),
    ])
    ids_per_model = {}
    for d in data_records:
        ids_per_model.setdefault(d.model, set()).add(d.res_id)

    for modello, ids in ids_per_model.items():
        records = env[modello].browse(list(ids)).exists()
        for record in records.with_context(lang='it_IT'):
            for campo in campi_per_model[modello]:
                valore = record[campo]
                if not valore:
                    continue
                nuovo = _sostituisci(valore)
                if nuovo != valore:
                    record.write({campo: nuovo})
                    contatori[modello] = contatori.get(modello, 0) + 1

    # 2) Nome del modello (ir.model.name) per i modelli del prefix hr.*
    #    e per i modelli con prefix hr_* (es. hr.employee, hr.department).
    modelli_hr = env['ir.model'].search([('model', '=like', 'hr.%')])
    for m in modelli_hr.with_context(lang='it_IT'):
        nuovo = _sostituisci(m.name)
        if nuovo != m.name:
            m.write({'name': nuovo})
            contatori['ir.model'] = contatori.get('ir.model', 0) + 1

    # 3) Label e help dei campi sui modelli hr.* (es. "Nome dipendente",
    #    "Dipendenti del dipartimento").
    campi_hr = env['ir.model.fields'].search([('model', '=like', 'hr.%')])
    for f in campi_hr.with_context(lang='it_IT'):
        vals = {}
        nuovo_label = _sostituisci(f.field_description)
        if nuovo_label != f.field_description:
            vals['field_description'] = nuovo_label
        if f.help:
            nuovo_help = _sostituisci(f.help)
            if nuovo_help != f.help:
                vals['help'] = nuovo_help
        if vals:
            f.write(vals)
            contatori['ir.model.fields'] = contatori.get('ir.model.fields', 0) + 1

    # 4) Label dei campi M2O/M2M che puntano a hr.* da altri modelli.
    #    Es: project.task.employee_id, account.analytic.line.employee_id
    #    hanno label "Dipendente" che vogliamo rinominare.
    campi_relazionali = env['ir.model.fields'].search([
        ('relation', '=like', 'hr.%'),
        ('model', 'not like', 'hr.%'),
    ])
    for f in campi_relazionali.with_context(lang='it_IT'):
        nuovo_label = _sostituisci(f.field_description)
        if nuovo_label != f.field_description:
            f.write({'field_description': nuovo_label})
            contatori['ir.model.fields.relazionali'] = (
                contatori.get('ir.model.fields.relazionali', 0) + 1
            )

    if contatori:
        _logger.info(
            "crocevia_hr_lexico: sostituzioni applicate: %s", contatori,
        )
    else:
        _logger.info(
            "crocevia_hr_lexico: nessuna sostituzione necessaria "
            "(forse il lessico era gia' stato applicato)."
        )
