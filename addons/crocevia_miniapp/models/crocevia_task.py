"""Le task dello staff dentro la miniapp, sopra il modulo Progetti di Odoo.

Le task sono quelle di Odoo (project.task): chi usa il gestionale le vede
e le cambia come sempre. Lo staff pero' quasi mai ha un utente Odoo, quindi
chi se ne occupa sta in un campo nostro, fatto di schede socio
(`miniapp_persone`), accanto agli assegnatari di Odoo. Si aggiungono una
checklist semplice e il collegamento a un'attivita' del calendario.

Chi puo' vedere e cambiare le task lo decide il server della miniapp (lo
staff, dai gruppi Telegram): qui si passa per sudo, come per la tessera.
"""
import base64
import re
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext, plaintext2html

ZONA = pytz.timezone('Europe/Rome')
STATI_CHIUSI = ('1_done', '1_canceled')
# La scadenza in Odoo e' un istante: dall'app arriva un giorno, e diventa
# quel giorno alle 18, l'ora in cui di solito si apre la sede.
ORA_SCADENZA = time(18, 0)
RIPETIZIONI = {'settimana': 'week', 'mese': 'month'}
FOTO_MAX = 12
COMMENTI_MAX = 40


class ProjectTask(models.Model):
    _inherit = 'project.task'

    miniapp_persone = fields.Many2many(
        'res.partner', 'crocevia_task_persona_rel', 'task_id', 'partner_id',
        string="Chi se ne occupa",
        domain="[('is_socio', '=', True)]",
        help="Le persone dello staff che seguono la task dalla miniapp: non "
             "serve che abbiano un utente Odoo. A loro arrivano i promemoria.")
    miniapp_voci = fields.One2many('crocevia.task.voce', 'task_id', string="Checklist", copy=True)
    miniapp_evento_titolo = fields.Char(string="Attività collegata")
    miniapp_evento_inizio = fields.Datetime(string="Quando è l'attività")
    miniapp_evento_sede = fields.Char(string="Sede dell'attività")
    miniapp_evento_id = fields.Char(string="Evento del calendario", copy=False)
    miniapp_creata_da = fields.Char(string="Creata dall'app da", copy=False, readonly=True)


class CroceviaTaskVoce(models.Model):
    _name = 'crocevia.task.voce'
    _description = "Voce della checklist di una task"
    _order = 'sequence, id'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade', index=True)
    name = fields.Char(string="Cosa", required=True)
    fatto = fields.Boolean(string="Fatto")
    sequence = fields.Integer(default=10)


class CroceviaMiniappTask(models.AbstractModel):
    _inherit = 'crocevia.miniapp'

    # ---------------- utilita' ----------------

    def _task(self, task_id):
        task = self.env['project.task'].sudo().browse(int(task_id)).exists()
        if not task or not task.project_id:
            raise UserError(_("Questa task non c’è più."))
        return task

    def _giorno_scadenza(self, task):
        if not task.date_deadline:
            return False
        locale = pytz.utc.localize(task.date_deadline).astimezone(ZONA)
        return locale.date()

    def _istante_scadenza(self, giorno):
        if not giorno:
            return False
        giorno = fields.Date.to_date(giorno)
        locale = ZONA.localize(datetime.combine(giorno, ORA_SCADENZA))
        return locale.astimezone(pytz.utc).replace(tzinfo=None)

    def _ripetizione(self, task):
        if not task.recurring_task:
            return False
        for chiave, unita in RIPETIZIONI.items():
            if task.repeat_unit == unita and task.repeat_interval == 1:
                return chiave
        return 'altro'

    def _persona(self, p):
        return {'id': p.id, 'nome': p.name}

    def _dati_task(self, task, partner=None):
        giorno = self._giorno_scadenza(task)
        voci = task.miniapp_voci
        foto = self.env['ir.attachment'].sudo().search_count([
            ('res_model', '=', 'project.task'), ('res_id', '=', task.id),
            ('mimetype', 'like', 'image/')])
        commenti = self.env['mail.message'].sudo().search_count([
            ('model', '=', 'project.task'), ('res_id', '=', task.id),
            ('message_type', '=', 'comment'), ('body', '!=', False)])
        return {
            'id': task.id,
            'nome': task.name,
            'progetto': {'id': task.project_id.id, 'nome': task.project_id.name},
            'scadenza': fields.Date.to_string(giorno) if giorno else False,
            'fatta': task.state in STATI_CHIUSI,
            'chiusa_il': fields.Date.to_string((task.date_end or task.write_date).date())
                         if task.state in STATI_CHIUSI else False,
            'importante': task.priority == '1',
            'etichette': [{'id': t.id, 'nome': t.name, 'colore': t.color} for t in task.tag_ids],
            'persone': [self._persona(p) for p in task.miniapp_persone],
            'mia': bool(partner and partner in task.miniapp_persone),
            'voci': {'fatte': len(voci.filtered('fatto')), 'tutte': len(voci)},
            'foto': foto,
            'commenti': commenti,
            'ripete': self._ripetizione(task),
            'evento': {
                'titolo': task.miniapp_evento_titolo,
                'inizio': fields.Datetime.to_string(task.miniapp_evento_inizio) if task.miniapp_evento_inizio else False,
                'sede': task.miniapp_evento_sede or '',
                'id': task.miniapp_evento_id or '',
            } if task.miniapp_evento_titolo else False,
        }

    # ---------------- lettura ----------------

    @api.model
    def task_opzioni(self):
        """Progetti ed etichette, per i filtri e il modulo."""
        self._controlla_accesso()
        progetti = self.env['project.project'].sudo().search([], order='sequence, name')
        etichette = self.env['project.tags'].sudo().search([], order='name')
        return {
            'progetti': [{'id': p.id, 'nome': p.name} for p in progetti],
            'etichette': [{'id': t.id, 'nome': t.name, 'colore': t.color} for t in etichette],
        }

    @api.model
    def task_elenco(self, telegram_id, fatte_da_giorni=0):
        """Le task aperte dei progetti, piu' quelle chiuse negli ultimi
        `fatte_da_giorni` giorni. Le to-do personali (senza progetto) no."""
        self._controlla_accesso()
        partner = self._socio(telegram_id)
        Task = self.env['project.task'].sudo()
        aperte = Task.search([('project_id', '!=', False), ('state', 'not in', STATI_CHIUSI)],
                             order='date_deadline asc, priority desc, id desc', limit=500)
        chiuse = Task.browse()
        if fatte_da_giorni:
            da = fields.Datetime.now() - timedelta(days=int(fatte_da_giorni))
            chiuse = Task.search([('project_id', '!=', False), ('state', '=', '1_done'),
                                  ('write_date', '>=', da)], order='write_date desc', limit=200)
        return [self._dati_task(t, partner) for t in aperte | chiuse]

    @api.model
    def task_dettaglio(self, task_id, telegram_id):
        self._controlla_accesso()
        task = self._task(task_id)
        dati = self._dati_task(task, self._socio(telegram_id))
        allegati = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'project.task'), ('res_id', '=', task.id),
            ('mimetype', 'like', 'image/')], order='id desc', limit=FOTO_MAX)
        messaggi = self.env['mail.message'].sudo().search([
            ('model', '=', 'project.task'), ('res_id', '=', task.id),
            ('message_type', '=', 'comment'), ('body', '!=', False)],
            order='id desc', limit=COMMENTI_MAX)
        dati.update({
            'descrizione': html2plaintext(task.description or '').strip(),
            'checklist': [{'id': v.id, 'nome': v.name, 'fatto': v.fatto} for v in task.miniapp_voci],
            'immagini': [{'id': a.id, 'nome': a.name, 'tipo': a.mimetype,
                          'dati': (a.datas or b'').decode()} for a in allegati],
            'messaggi': [{
                'id': m.id,
                'autore': m.author_id.name or '',
                'data': fields.Datetime.to_string(m.date),
                'testo': html2plaintext(m.body or '').strip(),
            } for m in reversed(messaggi) if html2plaintext(m.body or '').strip()],
            'descrizione_html': bool(task.description),
            'creata_da': task.miniapp_creata_da or (task.create_uid.name if task.create_uid else ''),
            'telegram': [p.telegram_id for p in task.miniapp_persone if p.telegram_id],
        })
        return dati

    # ---------------- scrittura ----------------

    def _etichette(self, ids, nuove):
        Tag = self.env['project.tags'].sudo()
        tags = Tag.browse([int(i) for i in ids or []]).exists()
        for nome in nuove or []:
            nome = str(nome).strip()[:40]
            if nome:
                tags |= Tag.search([('name', '=ilike', nome)], limit=1) or Tag.create({'name': nome})
        return tags

    @api.model
    def task_salva(self, telegram_id, valori, task_id=False, da_chi=''):
        """Crea una task, o ne cambia una. Dice a chi e' stata appena
        assegnata, per l'avviso in chat."""
        self._controlla_accesso()
        nome = str(valori.get('nome') or '').strip()
        if not nome:
            raise UserError(_("Dai un nome alla task."))
        progetto = self.env['project.project'].sudo().browse(int(valori.get('progetto_id') or 0)).exists()
        if not progetto:
            raise UserError(_("Scegli un progetto."))
        persone = self.env['res.partner'].sudo().browse(
            [int(i) for i in valori.get('persone') or []]).exists().filtered('is_socio')
        ripete = valori.get('ripete') or False
        if ripete and ripete not in RIPETIZIONI:
            raise UserError(_("Ripetizione sconosciuta."))
        if ripete and not valori.get('scadenza'):
            raise UserError(_("Una task che si ripete ha bisogno di una scadenza."))
        vals = {
            'name': nome[:200],
            'project_id': progetto.id,
            'date_deadline': self._istante_scadenza(valori.get('scadenza')),
            'priority': '1' if valori.get('importante') else '0',
            'miniapp_persone': [(6, 0, persone.ids)],
            'tag_ids': [(6, 0, self._etichette(valori.get('etichette'), valori.get('etichette_nuove')).ids)],
            'description': plaintext2html(str(valori.get('descrizione') or '').strip()[:4000])
                           if str(valori.get('descrizione') or '').strip() else False,
            'recurring_task': bool(ripete),
        }
        if ripete:
            vals.update(repeat_interval=1, repeat_unit=RIPETIZIONI[ripete], repeat_type='forever')
        evento = valori.get('evento') or False
        if evento and evento.get('titolo'):
            vals.update(miniapp_evento_titolo=str(evento['titolo'])[:200],
                        miniapp_evento_inizio=fields.Datetime.to_datetime(
                            str(evento.get('inizio') or '')[:19].replace('T', ' ')) if evento.get('inizio') else False,
                        miniapp_evento_sede=str(evento.get('sede') or '')[:60],
                        miniapp_evento_id=str(evento.get('id') or '')[:200])
        elif 'evento' in valori:
            vals.update(miniapp_evento_titolo=False, miniapp_evento_inizio=False,
                        miniapp_evento_sede=False, miniapp_evento_id=False)
        Task = self.env['project.task'].sudo()
        if task_id:
            task = self._task(task_id)
            prima = task.miniapp_persone
            # Odoo vuole la ricorrenza tolta prima di cambiare i suoi campi.
            if task.recurring_task and not ripete:
                task.write({'recurring_task': False})
            task.write(vals)
            task.message_post(body=_("Modificata dalla miniapp da %s.", da_chi or 'qualcuno'),
                              subtype_xmlid='mail.mt_note')
        else:
            prima = self.env['res.partner']
            vals['miniapp_creata_da'] = da_chi or False
            voci = [str(v).strip()[:200] for v in valori.get('checklist') or [] if str(v).strip()]
            vals['miniapp_voci'] = [(0, 0, {'name': v, 'sequence': i}) for i, v in enumerate(voci)]
            task = Task.with_context(mail_create_nosubscribe=True).create(vals)
            task.message_post(body=_("Creata dalla miniapp da %s.", da_chi or 'qualcuno'),
                              subtype_xmlid='mail.mt_note')
        nuove = task.miniapp_persone - prima
        chi = self._socio(telegram_id)
        return {
            'task': self._dati_task(task, chi),
            'avvisare': [{'telegram_id': p.telegram_id, 'nome': p.name}
                         for p in nuove if p.telegram_id and p != chi],
        }

    @api.model
    def task_prendo(self, telegram_id, task_id):
        """"Prendo io": chi chiede si aggiunge a chi se ne occupa."""
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        task = self._task(task_id)
        if socio not in task.miniapp_persone:
            task.write({'miniapp_persone': [(4, socio.id)]})
            task.message_post(body=_("%s se ne occupa (dalla miniapp).", socio.name),
                              subtype_xmlid='mail.mt_note')
        return self._dati_task(task, socio)

    @api.model
    def task_stato(self, telegram_id, task_id, fatta, da_chi=''):
        """Fatta o di nuovo aperta. Chiudendo una task che si ripete, Odoo
        crea da solo la prossima."""
        self._controlla_accesso()
        task = self._task(task_id)
        if fatta and task.state not in STATI_CHIUSI:
            task.write({'state': '1_done', 'date_end': fields.Datetime.now()})
            task.message_post(body=_("Fatta, segnata dalla miniapp da %s.", da_chi or 'qualcuno'),
                              subtype_xmlid='mail.mt_note')
        elif not fatta and task.state in STATI_CHIUSI:
            task.write({'state': '01_in_progress', 'date_end': False})
            task.message_post(body=_("Riaperta dalla miniapp da %s.", da_chi or 'qualcuno'),
                              subtype_xmlid='mail.mt_note')
        chi = self._socio(telegram_id)
        prossima = False
        if fatta and task.recurrence_id:
            dopo = self.env['project.task'].sudo().search([
                ('recurrence_id', '=', task.recurrence_id.id), ('id', '>', task.id)], limit=1, order='id desc')
            prossima = self._dati_task(dopo, chi) if dopo else False
        return {'task': self._dati_task(task, chi), 'prossima': prossima,
                'avvisare': [{'telegram_id': p.telegram_id, 'nome': p.name}
                             for p in task.miniapp_persone if p.telegram_id and p != chi]}

    @api.model
    def task_commenta(self, telegram_id, task_id, testo):
        self._controlla_accesso()
        testo = str(testo or '').strip()[:2000]
        if not testo:
            raise UserError(_("Scrivi qualcosa."))
        socio = self._socio_obbligatorio(telegram_id)
        task = self._task(task_id)
        task.message_post(body=plaintext2html(testo), message_type='comment',
                          subtype_xmlid='mail.mt_note', author_id=socio.id)
        return {'task': task.name,
                'avvisare': [{'telegram_id': p.telegram_id, 'nome': p.name}
                             for p in task.miniapp_persone if p.telegram_id and p != socio]}

    @api.model
    def task_foto(self, telegram_id, task_id, dati_base64, nome='foto.jpg'):
        """Una foto attaccata alla task (un guasto, uno scontrino): finisce
        anche nella cronologia della task in Odoo."""
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        task = self._task(task_id)
        try:
            dati = base64.b64decode(dati_base64, validate=True)
        except Exception:
            raise UserError(_("Questa foto non va: riprova."))
        if not dati.startswith(b'\xff\xd8') or len(dati) > 4 * 1024 * 1024:
            raise UserError(_("Questa foto non va: riprova."))
        nome = re.sub(r'[^\w.\- ]', '', str(nome or 'foto.jpg'))[:60] or 'foto.jpg'
        allegato = self.env['ir.attachment'].sudo().create({
            'name': nome, 'datas': dati_base64, 'mimetype': 'image/jpeg',
            'res_model': 'project.task', 'res_id': task.id,
        })
        task.message_post(body=_("Foto aggiunta dalla miniapp."),
                          subtype_xmlid='mail.mt_note', author_id=socio.id,
                          attachment_ids=[allegato.id])
        return {'id': allegato.id}

    @api.model
    def task_voce(self, task_id, azione, voce_id=False, testo=''):
        """La checklist: aggiungi una voce, spuntala (o togli la spunta),
        toglila."""
        self._controlla_accesso()
        task = self._task(task_id)
        Voce = self.env['crocevia.task.voce'].sudo()
        if azione == 'aggiungi':
            testo = str(testo or '').strip()[:200]
            if not testo:
                raise UserError(_("Scrivi la voce."))
            Voce.create({'task_id': task.id, 'name': testo,
                         'sequence': (max(task.miniapp_voci.mapped('sequence')) + 1) if task.miniapp_voci else 0})
        else:
            voce = Voce.browse(int(voce_id or 0)).exists()
            if not voce or voce.task_id != task:
                raise UserError(_("Questa voce non c’è più."))
            if azione == 'spunta':
                voce.fatto = not voce.fatto
            elif azione == 'togli':
                voce.unlink()
            else:
                raise UserError(_("Azione sconosciuta."))
        return [{'id': v.id, 'nome': v.name, 'fatto': v.fatto} for v in task.miniapp_voci]

    # ---------------- promemoria ----------------

    def _aperte_con_scadenza(self):
        return self.env['project.task'].sudo().search([
            ('project_id', '!=', False), ('state', 'not in', STATI_CHIUSI),
            ('date_deadline', '!=', False)], order='date_deadline')

    @api.model
    def task_promemoria(self):
        """Per il giro di ogni mattina: le task che scadono domani e quelle
        scadute ieri, con chi se ne occupa."""
        self._controlla_accesso()
        oggi = datetime.now(ZONA).date()
        out = []
        for t in self._aperte_con_scadenza():
            giorno = self._giorno_scadenza(t)
            if giorno == oggi + timedelta(days=1):
                quando = 'domani'
            elif giorno == oggi - timedelta(days=1):
                quando = 'ieri'
            else:
                continue
            out.append({'id': t.id, 'nome': t.name, 'progetto': t.project_id.name, 'quando': quando,
                        'persone': [{'telegram_id': p.telegram_id, 'nome': p.name}
                                    for p in t.miniapp_persone if p.telegram_id]})
        return out

    @api.model
    def task_settimana(self):
        """Per il riepilogo del lunedi': le task scadute e quelle che scadono
        nei prossimi sette giorni."""
        self._controlla_accesso()
        oggi = datetime.now(ZONA).date()
        out = []
        for t in self._aperte_con_scadenza():
            giorno = self._giorno_scadenza(t)
            if giorno > oggi + timedelta(days=7):
                break
            out.append({'id': t.id, 'nome': t.name, 'progetto': t.project_id.name,
                        'scadenza': fields.Date.to_string(giorno), 'scaduta': giorno < oggi,
                        'persone': [p.name for p in t.miniapp_persone]})
        return out
