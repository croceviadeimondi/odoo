"""API della miniapp Telegram, chiamata via XML-RPC dal server del calendario.

Chi chiama e' sempre l'utente tecnico "Miniapp": l'identita' della persona
arriva come `telegram_id`, gia' verificato dal server con l'initData di
Telegram. Allo stesso modo e' il server a sapere chi e' staff (chi sta nei
gruppi Telegram dello staff): i metodi da staff si fidano di lui, e il nome
di chi ha agito finisce nel chatter come `da_chi`.

Le regole dei prestiti stanno qui e non nel server: un prestito aperto per
socio, durata dai parametri di sistema. Valgono solo per la miniapp; da
Odoo lo staff resta libero di fare eccezioni.
"""
import random
import re
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

GRUPPO = 'crocevia_miniapp.group_crocevia_miniapp'

CAMPI_BENE = (
    'name', 'categoria', 'sede_id', 'codice_interno', 'sistema_id',
    'autore', 'editore', 'anno_pubblicazione', 'isbn', 'valore_stimato',
    'note', 'proprietario_id', 'proprietario_libero',
)


# Come si puo' ordinare il catalogo dall'app. Solo questi: l'ordine arriva
# da fuori e finisce in una query.
ORDINI = {
    'popolari': 'numero_prestiti desc, name, id',
    'recenti': 'create_date desc, id desc',
    'titolo': 'name, id',
    'autore': 'autore, name, id',
    'disponibili': 'stato_bene, numero_prestiti desc, name, id',
}


def _solo_cifre(isbn):
    return re.sub(r'[^0-9Xx]', '', isbn or '').upper()


def _isbn_equivalenti(cifre):
    """Lo stesso libro con l'ISBN a 10 e a 13 cifre: il codice a barre e'
    sempre a 13 (978...), in inventario a volte c'e' quello vecchio a 10."""
    uguali = {cifre}
    if len(cifre) == 13 and cifre.startswith('978') and cifre.isdigit():
        corpo = cifre[3:12]
        resto = sum((10 - i) * int(c) for i, c in enumerate(corpo)) % 11
        controllo = (11 - resto) % 11
        uguali.add(corpo + ('X' if controllo == 10 else str(controllo)))
    elif len(cifre) == 10 and cifre[:9].isdigit():
        corpo = '978' + cifre[:9]
        somma = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(corpo))
        uguali.add(corpo + str((10 - somma % 10) % 10))
    return uguali


class CroceviaMiniapp(models.AbstractModel):
    _name = 'crocevia.miniapp'
    _description = "API della miniapp Telegram"

    # ---------------- infrastruttura ----------------

    def _controlla_accesso(self):
        # Il modello e' raggiungibile via RPC da qualsiasi utente interno:
        # senza questo controllo un Membro potrebbe aprire prestiti a nome
        # di chiunque passando un telegram_id a caso.
        if not (self.env.su or self.env.user.has_group(GRUPPO)):
            raise AccessError(_("Questa API è riservata all'utente della miniapp."))

    def _param_int(self, chiave, default):
        valore = self.env['ir.config_parameter'].sudo().get_param(
            'crocevia_miniapp.' + chiave)
        try:
            return int(valore)
        except (TypeError, ValueError):
            return default

    def _socio(self, telegram_id):
        """La scheda collegata a quel Telegram, se e' un socio non cessato."""
        if not telegram_id:
            return self.env['res.partner']
        return self.env['res.partner'].search([
            ('telegram_id', '=', str(telegram_id)),
            ('is_socio', '=', True),
            ('stato_socio', '!=', 'cessato'),
        ], limit=1)

    def _socio_obbligatorio(self, telegram_id):
        socio = self._socio(telegram_id)
        if not socio:
            raise UserError(_("Non risulti sociə: registrati dalla miniapp."))
        return socio

    def _dati_socio(self, partner):
        return {
            'id': partner.id,
            'nome': partner.name,
            'numero_socio': partner.numero_socio or False,
        }

    def _dati_bene(self, bene, staff=False):
        dati = {
            'id': bene.id,
            'titolo': bene.name,
            'categoria': bene.categoria,
            'sede_id': bene.sede_id.id,
            'sede': bene.sede_id.citta,
            'codice_interno': bene.codice_interno or False,
            'autore': bene.autore or False,
            'editore': bene.editore or False,
            'anno': bene.anno_pubblicazione or False,
            'isbn': bene.isbn or False,
            'generi': bene.genere_ids.mapped('name'),
            'sistema': bene.sistema_id.name or False,
            'stato': bene.stato_bene,
        }
        # Chi ha il bene lo vede solo lo staff: nel catalogo dei soci basta
        # sapere che non c'e'.
        if staff and bene.prestito_corrente_id:
            prestito = bene.prestito_corrente_id
            dati['prestito'] = self._dati_prestito(prestito)
        return dati

    def _dati_prestito(self, prestito):
        return {
            'id': prestito.id,
            'bene_id': prestito.bene_id.id,
            'titolo': prestito.bene_id.name,
            'sede': prestito.bene_id.sede_id.citta,
            'socio': prestito.partner_id.name or prestito.prestatario_libero or '',
            'data_prestito': fields.Date.to_string(prestito.data_prestito),
            'scadenza': fields.Date.to_string(
                prestito.data_restituzione_prevista) or False,
            'stato': prestito.stato,
        }

    # ---------------- registrazione ----------------

    @api.model
    def socio_da_telegram(self, telegram_id):
        """Chi e' questo Telegram. False se non e' (o non e' piu') socio."""
        self._controlla_accesso()
        socio = self._socio(telegram_id)
        if not socio:
            return False
        return dict(self._dati_socio(socio), admin=socio.admin_miniapp)

    @api.model
    def informativa(self):
        """Il testo dell'informativa privacy dell'app.

        Quello di crocevia_gdpr e' per chi usa il gestionale; resta come
        riserva se il parametro dell'app manca. L'utente tecnico non legge
        i parametri di sistema: questi sono gli unici che gli servono.
        """
        self._controlla_accesso()
        Param = self.env['ir.config_parameter'].sudo()
        return (Param.get_param('crocevia_miniapp.informativa_html')
                or Param.get_param('crocevia_gdpr.informativa_html')
                or False)

    @api.model
    def candidati(self, nome, cognome):
        """Soci senza Telegram il cui nome somiglia a quello dichiarato.

        Servono allo staff per dire "e' lui" invece di creare un doppione.
        """
        self._controlla_accesso()
        dominio = [
            ('is_socio', '=', True),
            ('telegram_id', '=', False),
        ]
        for parola in (cognome or '', nome or ''):
            parola = parola.strip()
            if parola:
                dominio.append(('name', 'ilike', parola))
        soci = self.env['res.partner'].search(dominio, limit=3, order='name')
        return [self._dati_socio(s) for s in soci]

    def _controlla_telegram_libero(self, telegram_id):
        gia = self.env['res.partner'].search(
            [('telegram_id', '=', str(telegram_id))], limit=1)
        if gia:
            raise UserError(_(
                "Questo Telegram è già collegato a %s.", gia.display_name))

    @api.model
    def collega_socio(self, telegram_id, partner_id, privacy_data, da_chi):
        """Lo staff ha detto "e' lui": aggancia il Telegram alla scheda."""
        self._controlla_accesso()
        self._controlla_telegram_libero(telegram_id)
        socio = self.env['res.partner'].browse(int(partner_id)).exists()
        if not socio or not socio.is_socio:
            raise UserError(_("La scheda scelta non è di unə sociə."))
        if socio.telegram_id:
            raise UserError(_(
                "%s ha già un Telegram collegato.", socio.display_name))
        # sudo solo per questi due campi: se la scheda e' di qualcunə che ha
        # anche un utente Odoo (il direttivo, per esempio), Odoo 18 vuole il
        # permesso di modificare gli utenti, e l'utente tecnico non ce l'ha
        # apposta. Che sia unə sociə e' gia' controllato qui sopra.
        socio.sudo().write({
            'telegram_id': str(telegram_id),
            'miniapp_privacy_data': privacy_data or fields.Datetime.now(),
        })
        socio.message_post(body=_(
            "Telegram collegato dalla miniapp, confermato da %s.", da_chi), subtype_xmlid='mail.mt_note')
        return self._dati_socio(socio)

    @api.model
    def crea_socio(self, telegram_id, nome, cognome, privacy_data, da_chi):
        """Lo staff ha detto "socio nuovo".

        Nasce la scheda in stato Richiesta: numero socio e quota restano
        cosa della segreteria.
        """
        self._controlla_accesso()
        self._controlla_telegram_libero(telegram_id)
        nome_completo = ' '.join(
            p.strip() for p in (nome or '', cognome or '') if p.strip())
        if not nome_completo:
            raise UserError(_("Servono nome e cognome."))
        socio = self.env['res.partner'].create({
            'name': nome_completo,
            'is_socio': True,
            'stato_socio': 'richiesta',
            'telegram_id': str(telegram_id),
            'miniapp_privacy_data': privacy_data or fields.Datetime.now(),
        })
        socio.message_post(body=_(
            "Scheda creata dalla miniapp Telegram, sociə confermatə da %s.",
            da_chi), subtype_xmlid='mail.mt_note')
        return self._dati_socio(socio)

    # ---------------- catalogo ----------------

    # ---------------- registrazione provvisoria ----------------
    # Chi si registra dalla miniapp entra subito: nasce una scheda provvisoria
    # e il direttivo decide dopo. "Stessa persona" unisce la provvisoria alla
    # scheda vera e ci sposta i prestiti fatti nel frattempo; "socio nuovo"
    # tiene la provvisoria; "non e' socio" la archivia e chiude l'accesso.

    @api.model
    def registra_provvisorio(self, telegram_id, nome, cognome, privacy_data):
        self._controlla_accesso()
        self._controlla_telegram_libero(telegram_id)
        nome_completo = ' '.join(
            p.strip() for p in (nome or '', cognome or '') if p.strip())
        if not nome_completo:
            raise UserError(_("Servono nome e cognome."))
        socio = self.env['res.partner'].create({
            'name': nome_completo,
            'is_socio': True,
            'stato_socio': 'richiesta',
            'telegram_id': str(telegram_id),
            'miniapp_privacy_data': privacy_data or fields.Datetime.now(),
            'miniapp_provvisorio': True,
        })
        socio.message_post(body=_(
            "Registratə dalla miniapp Telegram: usa gia' l'app, il direttivo "
            "deve ancora confermare che sia sociə."), subtype_xmlid='mail.mt_note')
        return self._dati_socio(socio)

    def _provvisorio(self, provvisorio_id):
        prov = self.env['res.partner'].browse(int(provvisorio_id)).exists()
        if not prov or not prov.miniapp_provvisorio:
            raise UserError(_("Questa registrazione è già stata decisa."))
        return prov

    @api.model
    def conferma_provvisorio(self, provvisorio_id, partner_id, da_chi):
        """Il direttivo conferma. Senza `partner_id` e' sociə nuovə e la
        scheda provvisoria resta; con `partner_id` e' la stessa persona di una
        scheda che c'era gia': Telegram e prestiti passano a quella."""
        self._controlla_accesso()
        prov = self._provvisorio(provvisorio_id)
        if not partner_id:
            prov.sudo().write({'miniapp_provvisorio': False})
            prov.message_post(body=_(
                "Confermatə come sociə nuovə da %s.", da_chi), subtype_xmlid='mail.mt_note')
            return self._dati_socio(prov)

        socio = self.env['res.partner'].browse(int(partner_id)).exists()
        if not socio or not socio.is_socio or socio == prov:
            raise UserError(_("La scheda scelta non è di unə sociə."))
        if socio.telegram_id:
            raise UserError(_("%s ha già un Telegram collegato.", socio.display_name))
        telegram, privacy = prov.telegram_id, prov.miniapp_privacy_data
        prestiti = self.env['crocevia.prestito'].search([('partner_id', '=', prov.id)])
        prestiti.write({'partner_id': socio.id})
        # Il Telegram si toglie prima dalla provvisoria, ed e' scritto subito:
        # Odoo salva le modifiche in blocco, e il vincolo di unicita'
        # vedrebbe due schede con lo stesso Telegram.
        prov.sudo().write({'telegram_id': False, 'miniapp_provvisorio': False, 'active': False})
        prov.flush_recordset()
        socio.sudo().write({'telegram_id': telegram, 'miniapp_privacy_data': privacy})
        socio.message_post(body=_(
            "Telegram collegato dalla miniapp, confermato da %(chi)s. Spostati "
            "qui %(n)s prestiti fatti prima della conferma.",
            chi=da_chi, n=len(prestiti)), subtype_xmlid='mail.mt_note')
        prov.message_post(body=_(
            "Registrazione provvisoria unita alla scheda di %s.", socio.display_name),
            subtype_xmlid='mail.mt_note')
        return self._dati_socio(socio)

    @api.model
    def rifiuta_provvisorio(self, provvisorio_id, da_chi):
        """Il direttivo dice che non e' sociə: l'accesso si chiude. La scheda
        si archivia e non si cancella, perche' i prestiti aperti restano da
        recuperare e li vede chi amministra la biblioteca."""
        self._controlla_accesso()
        prov = self._provvisorio(provvisorio_id)
        prov.sudo().write({'telegram_id': False, 'miniapp_provvisorio': False,
                           'is_socio': False, 'active': False,
                           'miniapp_respinto_il': fields.Date.context_today(self)})
        prov.message_post(body=_(
            "Non riconosciutə come sociə da %s: accesso alla miniapp chiuso.", da_chi),
            subtype_xmlid='mail.mt_note')
        return True

    @api.model
    def opzioni(self):
        """Quello che serve per i filtri e per il form dei beni."""
        self._controlla_accesso()
        Bene = self.env['crocevia.bene']
        return {
            'sedi': [{'id': s.id, 'nome': s.citta}
                     for s in self.env['crocevia.sede'].search([])],
            'categorie': [{'id': k, 'nome': v} for k, v in
                          Bene._fields['categoria'].selection],
            'generi': [{'id': g.id, 'nome': g.name} for g in
                       self.env['crocevia.bene.genere'].search([])],
            'sistemi': [{'id': s.id, 'nome': s.name} for s in
                        self.env['crocevia.bene.sistema'].search([])],
            'giorni_prestito': self._param_int('giorni_prestito', 30),
            'max_prestiti': self._param_int('max_prestiti', 1),
        }

    def _dominio_testo(self, testo):
        """Ogni parola deve comparire da qualche parte: titolo, autore, ISBN
        o codice. Cosi' "rosa eco" trova "Il nome della rosa" di Eco, che
        cercato come frase intera non c'e'.

        Un ISBN si scrive senza trattini, ma in inventario spesso li ha: le
        parole fatte di sole cifre si confrontano anche ignorandoli.
        """
        dominio = []
        for parola in (testo or '').split()[:6]:
            alternative = [
                ('name', 'ilike', parola),
                ('autore', 'ilike', parola),
                ('isbn', 'ilike', parola),
                ('codice_interno', 'ilike', parola),
            ]
            cifre = _solo_cifre(parola)
            if len(cifre) >= 10 and cifre == parola.upper():
                uguali = _isbn_equivalenti(cifre)
                ids = self.env['crocevia.bene'].search([('isbn', '!=', False)]).filtered(
                    lambda b: _solo_cifre(b.isbn) in uguali).ids
                alternative.append(('id', 'in', ids))
            dominio += ['|'] * (len(alternative) - 1) + alternative
        return dominio

    def _inizio_parola(self, campo, parola):
        """Il campo ha una parola che comincia con `parola`: all'inizio, dopo
        uno spazio, un apostrofo o un trattino. "eco" trova "Eco Umberto" e
        "L'eco", non "seconda"."""
        p = parola.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        modelli = [p + '%', '% ' + p + '%', "%'" + p + '%', '%-' + p + '%', '%(' + p + '%']
        return ['|'] * (len(modelli) - 1) + [(campo, '=ilike', m) for m in modelli]

    @api.model
    def suggerimenti(self, testo, limite=8):
        """Quello che compare sotto la barra di ricerca mentre si scrive.

        Contano le parole che cominciano con quello che si e' scritto: ogni
        parola cercata deve aprire una parola del titolo o dell'autore.
        Prima i titoli che cominciano proprio cosi', poi gli altri. Solo se
        sono pochi si aggiungono i pezzi a meta' parola. Gli autori si
        propongono uno per uno, anche quando il bene ne ha dieci.
        """
        self._controlla_accesso()
        testo = (testo or '').strip()
        vuoto = {'beni': [], 'autori': [], 'generi': []}
        if len(testo) < 2:
            return vuoto
        limite = int(limite)
        parole = [p.lower() for p in testo.split()[:6]]
        Bene = self.env['crocevia.bene']

        dominio = []
        for parola in parole:
            alternative = (self._inizio_parola('name', parola)
                           + self._inizio_parola('autore', parola))
            dominio += ['|'] + alternative
        trovati = Bene.search(dominio, limit=200)

        def apre_parola(valore, parola):
            v = ' ' + re.sub(r"[\s'(\-]+", ' ', (valore or '').lower())
            return (' ' + parola) in v

        def peso(b):
            titolo = (b.name or '').lower()
            if titolo.startswith(' '.join(parole)):
                return (0, titolo)
            if all(apre_parola(b.name, p) for p in parole):
                return (1, titolo)
            return (2, titolo)

        beni = sorted(trovati, key=peso)[:limite]
        if len(beni) < limite:
            # Pochi risultati veri: si aggiungono i pezzi a meta' parola,
            # in fondo.
            altri = Bene.search(self._dominio_testo(testo) + [('id', 'not in', [b.id for b in beni])],
                                limit=limite - len(beni), order='name')
            beni += list(altri)

        autori = {}
        for riga in Bene.search_read(self._inizio_parola('autore', parole[0]), ['autore'], limit=300):
            for nome in re.split(r'[,;/]| e ', riga['autore']):
                nome = nome.strip()
                if nome and all(apre_parola(nome, p) for p in parole):
                    # "ECO Umberto" e "Eco Umberto" sono la stessa persona.
                    autori.setdefault(nome.lower(), nome)
        autori = sorted(autori.values(), key=lambda n: (not n.lower().startswith(parole[0]), n.lower()))[:3]

        generi = self.env['crocevia.bene.genere'].search(
            self._inizio_parola('name', parole[0]), limit=3)
        return {
            'beni': [{
                'id': b.id,
                'titolo': b.name,
                'autore': b.autore or False,
                'sede': b.sede_id.citta,
                'stato': b.stato_bene,
                'categoria': b.categoria,
            } for b in beni],
            'autori': autori,
            'generi': [{'id': g.id, 'nome': g.name} for g in generi],
        }

    @api.model
    def catalogo(self, filtri=None, offset=0, limit=50, staff=False, ordine='popolari', seme=0):
        self._controlla_accesso()
        filtri = filtri or {}
        dominio = self._dominio_testo(filtri.get('testo'))
        if filtri.get('bene_id'):
            dominio.append(('id', '=', int(filtri['bene_id'])))
        if filtri.get('autore'):
            # Un autore scelto dai suggerimenti: anche i beni dove e' uno dei
            # tanti.
            dominio.append(('autore', 'ilike', filtri['autore']))
        for campo in ('sede_id', 'sistema_id'):
            if filtri.get(campo):
                dominio.append((campo, '=', int(filtri[campo])))
        # Un tipo solo, o piu' di uno insieme (GdR e manuali stanno in una
        # scheda sola della biblioteca).
        categoria = filtri.get('categoria')
        if isinstance(categoria, (list, tuple)) and categoria:
            dominio.append(('categoria', 'in', list(categoria)))
        elif categoria:
            dominio.append(('categoria', '=', categoria))
        if filtri.get('genere_id'):
            dominio.append(('genere_ids', 'in', [int(filtri['genere_id'])]))
        if filtri.get('solo_disponibili'):
            dominio.append(('stato_bene', '=', 'disponibile'))
        Bene = self.env['crocevia.bene']
        offset, limit = int(offset), min(int(limit), 200)
        if ordine == 'casuale':
            # A caso, ma sempre fra quelli che rispettano i filtri, e sempre
            # nello stesso ordine per lo stesso seme: "Mostra altri" continua
            # la stessa estrazione invece di ripescare quelli gia' visti.
            ids = Bene.search(dominio, order='id').ids
            random.Random(int(seme or 0)).shuffle(ids)
            beni = Bene.browse(ids[offset:offset + limit])
        else:
            beni = Bene.search(dominio, offset=offset, limit=limit,
                               order=ORDINI.get(ordine, ORDINI['popolari']))
        return {
            'totale': Bene.search_count(dominio),
            'beni': [self._dati_bene(b, staff=staff) for b in beni],
        }

    @api.model
    def bene(self, bene_id, staff=False):
        self._controlla_accesso()
        bene = self.env['crocevia.bene'].browse(int(bene_id)).exists()
        if not bene:
            raise UserError(_("Questo bene non c'è più."))
        return self._dati_bene(bene, staff=staff)

    # ---------------- prestiti ----------------

    @api.model
    def presta(self, telegram_id, bene_id, note=False):
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        # Due "lo prendo io" nello stesso momento: il secondo aspetta il
        # primo qui, e poi trova il bene gia' in prestito invece di finire
        # contro il vincolo del modello con un errore incomprensibile.
        self.env.cr.execute(
            "SELECT id FROM crocevia_bene WHERE id = %s FOR UPDATE",
            [int(bene_id)])
        self.env.cr.execute(
            "SELECT id FROM res_partner WHERE id = %s FOR UPDATE", [socio.id])
        bene = self.env['crocevia.bene'].browse(int(bene_id)).exists()
        if not bene:
            raise UserError(_("Questo bene non c'è più."))
        bene.invalidate_recordset()
        if bene.mancante:
            raise UserError(_("Questo bene risulta mancante."))
        if bene.in_prestito:
            raise UserError(_("Qualcuno l'ha appena preso in prestito."))

        Prestito = self.env['crocevia.prestito']
        massimo = self._param_int('max_prestiti', 1)
        aperti = Prestito.search_count([
            ('partner_id', '=', socio.id),
            ('data_restituzione_effettiva', '=', False),
        ])
        if aperti >= massimo:
            raise UserError(_(
                "Hai già un prestito aperto: restituiscilo prima di "
                "prenderne un altro."))

        oggi = fields.Date.context_today(self)
        prestito = Prestito.create({
            'bene_id': bene.id,
            'partner_id': socio.id,
            'data_prestito': oggi,
            'data_restituzione_prevista': oggi + timedelta(
                days=self._param_int('giorni_prestito', 30)),
            'note': note or False,
        })
        prestito.message_post(body=_("Prestito aperto dallə sociə dalla miniapp."), subtype_xmlid='mail.mt_note')
        return self._dati_prestito(prestito)

    @api.model
    def annulla_prestito(self, telegram_id, prestito_id):
        """Il socio ha preso qualcosa per sbaglio e preme "Annulla" subito dopo:
        il prestito sparisce, come se non ci fosse mai stato, cosi' non conta
        fra i piu' presi e non resta nello storico.

        Solo il proprio, solo se ancora aperto, e solo nei primi due minuti:
        dopo e' un prestito vero, e si restituisce.
        """
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        prestito = self.env['crocevia.prestito'].browse(int(prestito_id)).exists()
        if not prestito or prestito.partner_id != socio or prestito.data_restituzione_effettiva:
            raise UserError(_("Non c'è un tuo prestito da annullare."))
        if fields.Datetime.now() - prestito.create_date > timedelta(minutes=2):
            raise UserError(_("È passato troppo tempo per annullarlo: restituiscilo."))
        bene = prestito.bene_id
        # L'utente tecnico non cancella prestiti: qui si', ma solo questo.
        prestito.sudo().unlink()
        bene.message_post(body=_(
            "Prestito annullato subito dallə sociə %s dalla miniapp.", socio.name),
            subtype_xmlid='mail.mt_note')
        return True

    @api.model
    def presta_a_nome(self, bene_id, nome, partner_id, da_chi, giorni=0):
        """Chi amministra la biblioteca segna che un bene l'ha preso qualcun
        altro: unə sociə (`partner_id`) o solo un nome. Il server la chiama
        solo per gli admin. Qui non vale il limite di un prestito a testa:
        e' una registrazione di quello che e' successo, non una richiesta."""
        self._controlla_accesso()
        self.env.cr.execute(
            "SELECT id FROM crocevia_bene WHERE id = %s FOR UPDATE", [int(bene_id)])
        bene = self.env['crocevia.bene'].browse(int(bene_id)).exists()
        if not bene:
            raise UserError(_("Questo bene non c'è più."))
        bene.invalidate_recordset()
        if bene.mancante:
            raise UserError(_("Questo bene risulta mancante."))
        if bene.in_prestito:
            raise UserError(_("È già in prestito."))
        partner = self.env['res.partner'].browse(int(partner_id)).exists() if partner_id else None
        nome = (nome or '').strip()
        if not partner and not nome:
            raise UserError(_("Scrivi chi l'ha preso."))
        oggi = fields.Date.context_today(self)
        prestito = self.env['crocevia.prestito'].create({
            'bene_id': bene.id,
            'partner_id': partner.id if partner else False,
            'prestatario_libero': False if partner else nome,
            'data_prestito': oggi,
            'data_restituzione_prevista': oggi + timedelta(
                days=int(giorni) or self._param_int('giorni_prestito', 30)),
        })
        prestito.message_post(body=_("Segnato dalla miniapp da %s.", da_chi),
                              subtype_xmlid='mail.mt_note')
        return self._dati_prestito(prestito)

    @api.model
    def miei_prestiti(self, telegram_id):
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        prestiti = self.env['crocevia.prestito'].search([
            ('partner_id', '=', socio.id),
            ('data_restituzione_effettiva', '=', False),
        ])
        return [self._dati_prestito(p) for p in prestiti]

    @api.model
    def restituisci(self, telegram_id, prestito_id):
        self._controlla_accesso()
        socio = self._socio_obbligatorio(telegram_id)
        prestito = self.env['crocevia.prestito'].browse(int(prestito_id)).exists()
        if not prestito or prestito.partner_id != socio:
            raise UserError(_("Non è un tuo prestito."))
        if prestito.data_restituzione_effettiva:
            return self._dati_prestito(prestito)
        prestito.action_restituisci()
        prestito.message_post(body=_(
            "Restituzione dichiarata dallə sociə dalla miniapp."), subtype_xmlid='mail.mt_note')
        return self._dati_prestito(prestito)

    @api.model
    def prolunga(self, prestito_id, giorni, da_chi):
        """Solo staff: il server lo chiama solo per chi sta nei gruppi staff."""
        self._controlla_accesso()
        prestito = self.env['crocevia.prestito'].browse(int(prestito_id)).exists()
        if not prestito or prestito.data_restituzione_effettiva:
            raise UserError(_("Questo prestito non è aperto."))
        giorni = int(giorni or self._param_int('giorni_prestito', 30))
        # Si parte da oggi se e' gia' scaduto: prolungare un prestito in
        # ritardo da due mesi deve dare tempo davvero.
        oggi = fields.Date.context_today(self)
        base = max(prestito.data_restituzione_prevista or oggi, oggi)
        prestito.data_restituzione_prevista = base + timedelta(days=giorni)
        prestito.message_post(body=_(
            "Prolungato di %(giorni)s giorni dalla miniapp da %(chi)s.",
            giorni=giorni, chi=da_chi), subtype_xmlid='mail.mt_note')
        return self._dati_prestito(prestito)

    @api.model
    def prestiti_aperti(self):
        """Tutti i prestiti in corso, per la vista degli admin della biblioteca:
        prima quelli in ritardo da piu' tempo.

        Il ritardo si conta qui e non dal campo `stato`, che e' salvato e si
        aggiorna solo quando cambiano le date.
        """
        self._controlla_accesso()
        oggi = fields.Date.context_today(self)
        prestiti = self.env['crocevia.prestito'].search(
            [('data_restituzione_effettiva', '=', False)],
            order='data_restituzione_prevista, data_prestito, id')
        risultato = []
        for p in prestiti:
            dati = self._dati_prestito(p)
            prevista = p.data_restituzione_prevista
            dati['giorni_ritardo'] = (oggi - prevista).days if prevista and prevista < oggi else 0
            risultato.append(dati)
        return risultato

    @api.model
    def chiudi_prestito(self, prestito_id, da_chi):
        """Un admin chiude un prestito a mano: il bene e' tornato, ma chi
        l'aveva non l'ha segnato dall'app."""
        self._controlla_accesso()
        prestito = self.env['crocevia.prestito'].browse(int(prestito_id)).exists()
        if not prestito:
            raise UserError(_("Questo prestito non c'è più."))
        if prestito.data_restituzione_effettiva:
            return self._dati_prestito(prestito)
        prestito.action_restituisci()
        prestito.message_post(body=_(
            "Chiuso a mano dalla miniapp da %s.", da_chi), subtype_xmlid='mail.mt_note')
        return self._dati_prestito(prestito)

    @api.model
    def riapri_prestito(self, prestito_id, da_chi):
        """Lo staff ha visto la foto della restituzione e il bene in sede non
        c'e': il prestito torna aperto, a nome di chi l'aveva."""
        self._controlla_accesso()
        prestito = self.env['crocevia.prestito'].browse(int(prestito_id)).exists()
        if not prestito:
            raise UserError(_("Questo prestito non c'è più."))
        riaperto = bool(prestito.data_restituzione_effettiva)
        if riaperto:
            # Se intanto qualcun altro l'ha preso, il bene in sede c'era: chi
            # ha ragione lo decide lo staff da Odoo, non un bottone.
            dopo = self.env['crocevia.prestito'].search([
                ('bene_id', '=', prestito.bene_id.id),
                ('data_restituzione_effettiva', '=', False),
            ], limit=1)
            if dopo:
                raise UserError(_(
                    "Nel frattempo l'ha preso %s: sistemalo da Odoo.",
                    dopo.partner_id.name or dopo.prestatario_libero or '?'))
            prestito.data_restituzione_effettiva = False
            prestito.message_post(body=_(
                "Riaperto dalla miniapp da %s: il bene non è rientrato in sede.", da_chi),
                subtype_xmlid='mail.mt_note')
        return dict(self._dati_prestito(prestito), riaperto=riaperto,
                    telegram_id=prestito.partner_id.telegram_id or False)

    @api.model
    def scaduti(self):
        """Prestiti aperti con la scadenza oggi o gia' passata.

        Per i promemoria del lunedi: il bot scrive ai soci che hanno un
        telegram_id e allo staff della sede del bene.
        """
        self._controlla_accesso()
        oggi = fields.Date.context_today(self)
        prestiti = self.env['crocevia.prestito'].search([
            ('data_restituzione_effettiva', '=', False),
            ('data_restituzione_prevista', '<=', oggi),
        ], order='data_restituzione_prevista')
        risultato = []
        for p in prestiti:
            dati = self._dati_prestito(p)
            dati['telegram_id'] = p.partner_id.telegram_id or False
            dati['giorni_ritardo'] = (oggi - p.data_restituzione_prevista).days
            risultato.append(dati)
        return risultato

    @api.model
    def in_scadenza(self, giorni=3):
        """Prestiti aperti che scadono esattamente fra `giorni` giorni, per il
        promemoria di qualche giorno prima: il bot gira una volta al giorno,
        quindi ognuno lo riceve una volta sola."""
        self._controlla_accesso()
        giorno = fields.Date.context_today(self) + timedelta(days=int(giorni))
        prestiti = self.env['crocevia.prestito'].search([
            ('data_restituzione_effettiva', '=', False),
            ('data_restituzione_prevista', '=', giorno),
            ('partner_id.telegram_id', '!=', False),
        ])
        return [dict(self._dati_prestito(p), telegram_id=p.partner_id.telegram_id)
                for p in prestiti]

    @api.model
    def _pulisci_respinti(self):
        """Dal cron. Le schede di chi e' stato respinto o ha chiesto di
        cancellare i dati, passati i mesi di conservazione: senza prestiti si
        cancellano, con prestiti (tutti chiusi) restano anonime, perche' lo
        storico dei beni ne ha bisogno. Chi ha un utente Odoo non si tocca."""
        mesi = self._param_int('mesi_conservazione_respinti', 6)
        limite = fields.Date.context_today(self) - relativedelta(months=mesi)
        Prestito = self.env['crocevia.prestito'].sudo()
        schede = self.env['res.partner'].sudo().with_context(active_test=False).search([
            ('miniapp_respinto_il', '!=', False),
            ('miniapp_respinto_il', '<=', limite),
            ('active', '=', False),
            ('telegram_id', '=', False),
        ])
        cancellate = anonime = 0
        for p in schede:
            if p.user_ids:
                continue
            prestiti = Prestito.search([('partner_id', '=', p.id)])
            if prestiti.filtered(lambda x: not x.data_restituzione_effettiva):
                continue
            if not prestiti:
                try:
                    with self.env.cr.savepoint():
                        p.unlink()
                    cancellate += 1
                    continue
                except Exception:
                    pass  # qualcosa la usa ancora: si rende anonima
            p.message_ids.unlink()
            p.write({'name': _("Ex utente app %s", p.id), 'email': False, 'phone': False,
                     'miniapp_respinto_il': False, 'miniapp_privacy_data': False})
            anonime += 1
        return {'cancellate': cancellate, 'anonime': anonime}

    # ---------------- aggiunta beni (staff) ----------------

    @api.model
    def stesso_isbn(self, isbn, sede_id=False):
        """Beni gia' in inventario con quell'ISBN, trattini e spazi a parte."""
        self._controlla_accesso()
        cercato = _solo_cifre(isbn)
        if not cercato:
            return []
        dominio = [('isbn', '!=', False)]
        if sede_id:
            dominio.append(('sede_id', '=', int(sede_id)))
        beni = self.env['crocevia.bene'].search(dominio).filtered(
            lambda b: _solo_cifre(b.isbn) == cercato)
        return [self._dati_bene(b) for b in beni]

    @api.model
    def cerca_soci(self, testo):
        """Per scegliere il proprietario di un bene."""
        self._controlla_accesso()
        soci = self.env['res.partner'].search(
            [('is_socio', '=', True), ('name', 'ilike', testo or '')],
            limit=10, order='name')
        return [self._dati_socio(s) for s in soci]

    def _trova_o_crea(self, modello, nome):
        nome = (nome or '').strip()
        if not nome:
            raise UserError(_("Serve un nome."))
        # =ilike: "fantasy" e "Fantasy" sono lo stesso genere.
        esistente = self.env[modello].search([('name', '=ilike', nome)], limit=1)
        return esistente or self.env[modello].create({'name': nome})

    @api.model
    def crea_genere(self, nome):
        self._controlla_accesso()
        genere = self._trova_o_crea('crocevia.bene.genere', nome)
        return {'id': genere.id, 'nome': genere.name}

    @api.model
    def crea_sistema(self, nome):
        self._controlla_accesso()
        sistema = self._trova_o_crea('crocevia.bene.sistema', nome)
        return {'id': sistema.id, 'nome': sistema.name}

    @api.model
    def crea_bene(self, valori, da_chi):
        self._controlla_accesso()
        # Solo i campi del form: il resto (mancante, prestiti, active) non
        # si tocca dalla miniapp.
        vals = {k: valori[k] for k in CAMPI_BENE if valori.get(k) not in (None, '')}
        if valori.get('genere_ids'):
            vals['genere_ids'] = [(6, 0, [int(g) for g in valori['genere_ids']])]
        if not vals.get('name') or not vals.get('sede_id'):
            raise UserError(_("Servono almeno titolo e sede."))
        bene = self.env['crocevia.bene'].create(vals)
        bene.message_post(body=_("Aggiunto dalla miniapp da %s.", da_chi), subtype_xmlid='mail.mt_note')
        return self._dati_bene(bene, staff=True)

    @api.model
    def bene_da_modificare(self, bene_id):
        """I valori grezzi del bene, per riempire il form della modifica."""
        self._controlla_accesso()
        bene = self.env['crocevia.bene'].browse(int(bene_id)).exists()
        if not bene:
            raise UserError(_("Questo bene non c'è più."))
        return {
            'id': bene.id,
            'name': bene.name,
            'categoria': bene.categoria,
            'sede_id': bene.sede_id.id,
            'autore': bene.autore or '',
            'editore': bene.editore or '',
            'anno_pubblicazione': bene.anno_pubblicazione or '',
            'isbn': bene.isbn or '',
            'codice_interno': bene.codice_interno or '',
            'valore_stimato': bene.valore_stimato or '',
            'proprietario_libero': bene.proprietario_libero or '',
            'note': bene.note or '',
            'genere_ids': bene.genere_ids.ids,
            'sistema_id': bene.sistema_id.id or False,
            'mancante': bene.mancante,
        }

    @api.model
    def modifica_bene(self, bene_id, valori, da_chi):
        """Solo admin della biblioteca. I campi sono quelli del form: un campo
        vuoto svuota, uno che non c'e' resta com'e'."""
        self._controlla_accesso()
        bene = self.env['crocevia.bene'].browse(int(bene_id)).exists()
        if not bene:
            raise UserError(_("Questo bene non c'è più."))
        vals = {k: valori[k] or False for k in CAMPI_BENE
                if k in valori and k != 'proprietario_id'}
        if 'name' in vals and not vals['name']:
            raise UserError(_("Manca il titolo."))
        if 'sede_id' in vals and not vals['sede_id']:
            raise UserError(_("Manca la sede."))
        if 'genere_ids' in valori:
            vals['genere_ids'] = [(6, 0, [int(g) for g in valori['genere_ids'] or []])]
        if 'mancante' in valori:
            vals['mancante'] = bool(valori['mancante'])
        bene.write(vals)
        bene.message_post(body=_("Modificato dalla miniapp da %s.", da_chi), subtype_xmlid='mail.mt_note')
        return self._dati_bene(bene, staff=True)

    # ---------------- dati personali (dal bot) ----------------

    def _scheda_telegram(self, telegram_id):
        # Anche archiviata o cessata: chi chiede i propri dati li ha anche
        # se non usa piu' l'app.
        if not telegram_id:
            return self.env['res.partner']
        return self.env['res.partner'].with_context(active_test=False).search(
            [('telegram_id', '=', str(telegram_id))], limit=1)

    @api.model
    def dati_personali(self, telegram_id):
        """Quello che l'app tiene di una persona, per /imieidati."""
        self._controlla_accesso()
        p = self._scheda_telegram(telegram_id)
        if not p:
            return False
        Prestito = self.env['crocevia.prestito']
        aperto = Prestito.search([('partner_id', '=', p.id),
                                  ('data_restituzione_effettiva', '=', False)], limit=1)
        return {
            'nome': p.name,
            'telegram_id': p.telegram_id,
            'privacy': fields.Datetime.to_string(p.miniapp_privacy_data) or False,
            'provvisorio': p.miniapp_provvisorio,
            'socio': p.is_socio and p.stato_socio != 'cessato',
            'numero_socio': p.numero_socio or False,
            'admin': p.admin_miniapp,
            'prestito': self._dati_prestito(aperto) if aperto else False,
            'prestiti_totali': Prestito.search_count([('partner_id', '=', p.id)]),
        }

    @api.model
    def cancella_dati(self, telegram_id):
        """La persona chiede di togliere i suoi dati dall'app.

        Subito si stacca il Telegram, e con lui l'accesso e i promemoria. Una
        scheda provvisoria, che il direttivo non ha mai confermato, si
        archivia. Il libro soci e lo storico dei prestiti hanno obblighi di
        conservazione loro: li valuta la segreteria, che il bot avvisa.
        """
        self._controlla_accesso()
        p = self._scheda_telegram(telegram_id)
        if not p:
            return False
        aperto = self.env['crocevia.prestito'].search(
            [('partner_id', '=', p.id), ('data_restituzione_effettiva', '=', False)], limit=1)
        if aperto:
            raise UserError(_(
                "Hai ancora “%s” in prestito: riportalo, poi riprova.", aperto.bene_id.name))
        provvisorio = p.miniapp_provvisorio
        vals = {'telegram_id': False, 'miniapp_privacy_data': False, 'admin_miniapp': False,
                'miniapp_provvisorio': False}
        if provvisorio:
            vals.update(is_socio=False, active=False,
                        miniapp_respinto_il=fields.Date.context_today(self))
        p.sudo().write(vals)
        p.message_post(body=_(
            "Ha chiesto dal bot di cancellare i suoi dati dall'app: Telegram scollegato%s. "
            "Libro soci e storico dei prestiti li valuta la segreteria.",
            _(" e scheda provvisoria archiviata") if provvisorio else ''),
            subtype_xmlid='mail.mt_note')
        return {'id': p.id, 'nome': p.name, 'provvisorio': provvisorio}
