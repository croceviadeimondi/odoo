from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMiniapp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.utente = cls.env.ref('crocevia_miniapp.user_miniapp')
        cls.api = cls.env['crocevia.miniapp'].with_user(cls.utente)
        cls.sede = cls.env['crocevia.sede'].create({'citta': 'Sede di prova'})
        Bene = cls.env['crocevia.bene']
        cls.libro = Bene.create({
            'name': 'Il nome della rosa', 'categoria': 'libro',
            'sede_id': cls.sede.id, 'isbn': '978-88-452-1234-5'})
        cls.gioco = Bene.create({
            'name': 'Carcassonne', 'categoria': 'gioco_da_tavolo',
            'sede_id': cls.sede.id})
        Partner = cls.env['res.partner']
        cls.mario = Partner.create({
            'name': 'Mario Rossi', 'is_socio': True, 'stato_socio': 'attivo',
            'telegram_id': '111'})
        cls.anna = Partner.create({
            'name': 'Anna Bianchi', 'is_socio': True, 'stato_socio': 'attivo',
            'telegram_id': '222'})
        cls.senza_telegram = Partner.create({
            'name': 'Luca Rossi', 'is_socio': True, 'stato_socio': 'attivo'})

    def test_solo_utente_miniapp(self):
        interno = self.env['res.users'].create({
            'name': 'Un membro', 'login': 'membro_prova',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['crocevia.miniapp'].with_user(interno).socio_da_telegram('111')

    def test_socio_da_telegram(self):
        self.assertEqual(self.api.socio_da_telegram('111')['id'], self.mario.id)
        self.assertFalse(self.api.socio_da_telegram('999'))
        self.mario.stato_socio = 'cessato'
        self.assertFalse(self.api.socio_da_telegram('111'))

    def test_informativa(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('crocevia_gdpr.informativa_html', '<p>Gestionale</p>')
        Param.set_param('crocevia_miniapp.informativa_html', '<p>App</p>')
        self.assertEqual(self.api.informativa(), '<p>App</p>')
        Param.set_param('crocevia_miniapp.informativa_html', False)
        self.assertEqual(self.api.informativa(), '<p>Gestionale</p>')

    def test_candidati_esclude_chi_ha_telegram(self):
        ids = [c['id'] for c in self.api.candidati('', 'Rossi')]
        self.assertIn(self.senza_telegram.id, ids)
        self.assertNotIn(self.mario.id, ids)

    def test_collega_socio(self):
        self.api.collega_socio('333', self.senza_telegram.id, False, 'Staff')
        self.assertEqual(self.senza_telegram.telegram_id, '333')
        self.assertTrue(self.senza_telegram.miniapp_privacy_data)
        # Lo stesso Telegram non si aggancia a una seconda scheda.
        with self.assertRaises(UserError):
            self.api.crea_socio('333', 'Altro', 'Nome', False, 'Staff')

    def test_collega_socio_con_utente_odoo(self):
        # Il direttivo ha un utente Odoo: la sua scheda non si modifica
        # senza i permessi sugli utenti, che l'utente tecnico non ha.
        utente = self.env['res.users'].create({
            'name': 'Membro del direttivo', 'login': 'direttivo_prova',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        utente.partner_id.write({'is_socio': True, 'stato_socio': 'attivo'})
        self.api.collega_socio('555', utente.partner_id.id, False, 'Staff')
        self.assertEqual(utente.partner_id.telegram_id, '555')

    def test_crea_socio(self):
        dati = self.api.crea_socio('444', ' Giulia ', 'Verdi', False, 'Staff')
        socio = self.env['res.partner'].browse(dati['id'])
        self.assertEqual(socio.name, 'Giulia Verdi')
        self.assertTrue(socio.is_socio)
        self.assertEqual(socio.stato_socio, 'richiesta')
        self.assertFalse(socio.numero_socio)

    def test_telegram_vuoto_non_collide(self):
        Partner = self.env['res.partner']
        a = Partner.create({'name': 'A', 'telegram_id': ''})
        b = Partner.create({'name': 'B', 'telegram_id': '  '})
        self.assertFalse(a.telegram_id)
        self.assertFalse(b.telegram_id)

    def test_presta_e_restituisci(self):
        prestito = self.api.presta('111', self.libro.id)
        oggi = fields.Date.context_today(self.libro)
        self.assertEqual(prestito['scadenza'],
                         fields.Date.to_string(oggi + timedelta(days=30)))
        self.assertEqual(self.libro.stato_bene, 'in_prestito')
        self.assertEqual(len(self.api.miei_prestiti('111')), 1)
        self.api.restituisci('111', prestito['id'])
        self.assertEqual(self.libro.stato_bene, 'disponibile')
        self.assertFalse(self.api.miei_prestiti('111'))

    def test_un_prestito_per_socio(self):
        self.api.presta('111', self.libro.id)
        with self.assertRaises(UserError):
            self.api.presta('111', self.gioco.id)

    def test_bene_gia_in_prestito(self):
        self.api.presta('111', self.libro.id)
        with self.assertRaises(UserError):
            self.api.presta('222', self.libro.id)

    def test_non_socio_non_presta(self):
        with self.assertRaises(UserError):
            self.api.presta('999', self.libro.id)

    def test_restituisce_solo_i_suoi(self):
        prestito = self.api.presta('111', self.libro.id)
        with self.assertRaises(UserError):
            self.api.restituisci('222', prestito['id'])

    def test_catalogo_nasconde_il_prestatario(self):
        self.api.presta('111', self.libro.id)
        filtri = {'testo': 'rosa', 'sede_id': self.sede.id}
        socio = self.api.catalogo(filtri)['beni'][0]
        self.assertEqual(socio['stato'], 'in_prestito')
        self.assertNotIn('prestito', socio)
        staff = self.api.catalogo(filtri, staff=True)['beni'][0]
        self.assertEqual(staff['prestito']['socio'], 'Mario Rossi')

    def test_ricerca_per_parole(self):
        # Le parole in ordine sparso, e l'ISBN senza trattini.
        filtri = {'sede_id': self.sede.id}
        self.assertEqual([b['id'] for b in self.api.catalogo(
            dict(filtri, testo='rosa nome'))['beni']], [self.libro.id])
        self.assertEqual([b['id'] for b in self.api.catalogo(
            dict(filtri, testo='9788845212345'))['beni']], [self.libro.id])

    def test_suggerimenti(self):
        self.libro.autore = 'Eco Umberto'
        self.env['crocevia.bene'].create({
            'name': 'Rosa dei venti di prova', 'categoria': 'libro',
            'sede_id': self.sede.id, 'autore': 'ECO Umberto'})
        s = self.api.suggerimenti('rosa')
        titoli = [b['titolo'] for b in s['beni']]
        # Prima chi comincia con la parola cercata.
        self.assertLess(titoli.index('Rosa dei venti di prova'),
                        titoli.index('Il nome della rosa'))
        autori = self.api.suggerimenti('eco umb')['autori']
        self.assertEqual(len([a for a in autori if a.lower() == 'eco umberto']), 1)
        # Un pezzo a meta' parola ("seconda") viene dopo chi comincia per "eco".
        self.env['crocevia.bene'].create({
            'name': 'La seconda di prova', 'categoria': 'libro', 'sede_id': self.sede.id})
        titoli = [b['titolo'] for b in self.api.suggerimenti('eco', limite=50)['beni']]
        if 'La seconda di prova' in titoli:
            self.assertLess(titoli.index('Il nome della rosa'), titoli.index('La seconda di prova'))
        # Di un bene con tanti autori si propone solo quello cercato.
        self.libro.autore = 'Mario Bianchi, Umberto Eco, Anna Verdi'
        self.assertIn('Umberto Eco', self.api.suggerimenti('umberto')['autori'])
        self.assertEqual(self.api.suggerimenti('r'), {'beni': [], 'autori': [], 'generi': []})

    def test_prolunga_parte_da_oggi_se_scaduto(self):
        prestito = self.api.presta('111', self.libro.id)
        record = self.env['crocevia.prestito'].browse(prestito['id'])
        oggi = fields.Date.context_today(record)
        record.data_restituzione_prevista = oggi - timedelta(days=60)
        dati = self.api.prolunga(prestito['id'], 30, 'Staff')
        self.assertEqual(dati['scadenza'],
                         fields.Date.to_string(oggi + timedelta(days=30)))

    def test_scaduti(self):
        prestito = self.api.presta('111', self.libro.id)
        self.assertFalse(self.api.scaduti())
        record = self.env['crocevia.prestito'].browse(prestito['id'])
        record.data_restituzione_prevista = fields.Date.context_today(record)
        scaduti = self.api.scaduti()
        self.assertEqual(len(scaduti), 1)
        self.assertEqual(scaduti[0]['telegram_id'], '111')
        self.assertEqual(scaduti[0]['giorni_ritardo'], 0)

    def test_stesso_isbn_ignora_trattini(self):
        trovati = self.api.stesso_isbn('9788845212345', self.sede.id)
        self.assertEqual([b['id'] for b in trovati], [self.libro.id])

    def test_crea_genere_senza_doppioni(self):
        a = self.api.crea_genere('Fantascienza di prova')
        b = self.api.crea_genere('fantascienza di prova')
        self.assertEqual(a['id'], b['id'])

    def test_crea_bene(self):
        genere = self.api.crea_genere('Saggi di prova')
        dati = self.api.crea_bene({
            'name': 'Un libro nuovo', 'categoria': 'libro',
            'sede_id': self.sede.id, 'isbn': '9780000000002',
            'genere_ids': [genere['id']], 'mancante': True,
        }, 'Staff')
        bene = self.env['crocevia.bene'].browse(dati['id'])
        self.assertEqual(bene.genere_ids.ids, [genere['id']])
        # I campi fuori dal form non passano.
        self.assertFalse(bene.mancante)
        with self.assertRaises(UserError):
            self.api.crea_bene({'name': 'Senza sede'}, 'Staff')
