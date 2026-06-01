"""
Wizard per esportare i volontari attivi a una certa data in CSV
formattato per la compagnia assicurativa (separatore `;`, BOM UTF-8
per Excel italiano).
"""

import base64
import csv
import io

from odoo import api, fields, models, _


TIPO_FILTRO_SELECTION = [
    ('abituali', 'Solo volontari abituali'),
    ('occasionali', 'Solo volontari occasionali'),
    ('entrambi', 'Entrambi'),
]


class CroceviaRegistroExportWizard(models.TransientModel):
    _name = 'crocevia.registro.export.wizard'
    _description = "Esporta volontari per compagnia assicurativa"

    data_riferimento = fields.Date(
        string="Data di riferimento",
        required=True,
        default=fields.Date.context_today,
        help="Saranno inclusi i volontari iscritti a questa data "
             "(data_inizio <= riferimento, data_fine vuota o >= riferimento).",
    )
    tipo_filtro = fields.Selection(
        selection=TIPO_FILTRO_SELECTION,
        string="Tipo",
        default='entrambi',
        required=True,
    )
    file_csv = fields.Binary(string="File CSV", readonly=True)
    file_nome = fields.Char(string="Nome file", readonly=True)

    def action_genera(self):
        self.ensure_one()
        Isc = self.env['crocevia.registro.iscrizione']
        domain = [
            ('data_inizio_attivita', '<=', self.data_riferimento),
            '|',
            ('data_fine_attivita', '=', False),
            ('data_fine_attivita', '>=', self.data_riferimento),
            ('annullamento_id', '=', False),
        ]
        if self.tipo_filtro != 'entrambi':
            tipo = 'abituale' if self.tipo_filtro == 'abituali' else 'occasionale'
            domain.append(('tipo', '=', tipo))

        records = Isc.search(domain, order='numero_iscrizione asc')

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            'Numero iscrizione', 'Cognome', 'Nome', 'Codice fiscale',
            'Data di nascita', 'Luogo di nascita',
            'Indirizzo residenza', 'CAP', 'Citta', 'Provincia',
            'Tipo', 'Data inizio attivita', 'Data fine attivita',
            'Stato',
        ])
        for r in records:
            writer.writerow([
                '%06d' % r.numero_iscrizione,
                r.cognome or '',
                r.nome or '',
                r.codice_fiscale or '',
                r.data_nascita.strftime('%d/%m/%Y') if r.data_nascita else '',
                r.luogo_nascita or '',
                r.indirizzo_residenza or '',
                r.cap_residenza or '',
                r.citta_residenza or '',
                r.provincia_residenza or '',
                dict(r._fields['tipo'].selection).get(r.tipo, r.tipo),
                r.data_inizio_attivita.strftime('%d/%m/%Y') if r.data_inizio_attivita else '',
                r.data_fine_attivita.strftime('%d/%m/%Y') if r.data_fine_attivita else '',
                dict(r._fields['stato'].selection).get(r.stato, r.stato),
            ])
        # BOM UTF-8 per compatibilita' Excel italiano (codifica corretta
        # accenti e caratteri speciali al doppio click).
        bom = '﻿'
        contenuto = (bom + buf.getvalue()).encode('utf-8')
        self.file_csv = base64.b64encode(contenuto)
        self.file_nome = "volontari_%s.csv" % self.data_riferimento.strftime('%Y%m%d')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crocevia.registro.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
