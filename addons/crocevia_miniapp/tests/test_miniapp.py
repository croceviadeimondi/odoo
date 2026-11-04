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

    def test_registrazione_provvisoria_unita(self):
        prov = self.api.registra_provvisorio('777', 'Luca', 'Rossi', False)
        # Entra subito e prende un libro.
        self.assertEqual(self.api.socio_da_telegram('777')['id'], prov['id'])
        prestito = self.api.presta('777', self.libro.id)
        # Il direttivo dice: e' la stessa persona di Luca Rossi.
        socio = self.api.conferma_provvisorio(prov['id'], self.senza_telegram.id, 'Direttivo')
        self.assertEqual(socio['id'], self.senza_telegram.id)
        self.assertEqual(self.senza_telegram.telegram_id, '777')
        self.assertEqual(self.env['crocevia.prestito'].browse(prestito['id']).partner_id,
                         self.senza_telegram)
        provvisoria = self.env['res.partner'].with_context(active_test=False).browse(prov['id'])
        self.assertFalse(provvisoria.active)
        self.assertEqual(self.api.socio_da_telegram('777')['id'], self.senza_telegram.id)
        with self.assertRaises(UserError):
            self.api.conferma_provvisorio(prov['id'], False, 'Direttivo')

    def test_registrazione_provvisoria_nuova_e_rifiutata(self):
        prov = self.api.registra_provvisorio('778', 'Nuova', 'Persona', False)
        self.api.conferma_provvisorio(prov['id'], False, 'Direttivo')
        scheda = self.env['res.partner'].browse(prov['id'])
        self.assertFalse(scheda.miniapp_provvisorio)
        self.assertEqual(self.api.socio_da_telegram('778')['id'], prov['id'])

        prov = self.api.registra_provvisorio('779', 'Non', 'Socio', False)
        self.api.rifiuta_provvisorio(prov['id'], 'Direttivo')
        self.assertFalse(self.api.socio_da_telegram('779'))

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

    def test_annulla_prestito(self):
        prestito = self.api.presta('111', self.libro.id)
        with self.assertRaises(UserError):
            self.api.annulla_prestito('222', prestito['id'])
        self.assertTrue(self.api.annulla_prestito('111', prestito['id']))
        self.assertFalse(self.env['crocevia.prestito'].browse(prestito['id']).exists())
        self.assertEqual(self.libro.stato_bene, 'disponibile')
        self.assertEqual(self.libro.numero_prestiti, 0)
        # Dopo due minuti no.
        prestito = self.api.presta('111', self.libro.id)
        self.env.cr.execute("UPDATE crocevia_prestito SET create_date = now() - interval '5 minutes' WHERE id = %s",
                            [prestito['id']])
        self.env['crocevia.prestito'].invalidate_model(['create_date'])
        with self.assertRaises(UserError):
            self.api.annulla_prestito('111', prestito['id'])

    def test_presta_a_nome(self):
        # Un nome senza scheda.
        p = self.api.presta_a_nome(self.libro.id, 'Ospite Gentile', False, 'Admin')
        self.assertEqual(p['socio'], 'Ospite Gentile')
        self.assertEqual(self.libro.stato_bene, 'in_prestito')
        with self.assertRaises(UserError):
            self.api.presta_a_nome(self.libro.id, 'Altro', False, 'Admin')
        self.assertIn(p['id'], [x['id'] for x in self.api.prestiti_aperti()])
        self.api.chiudi_prestito(p['id'], 'Admin')
        # A unə sociə, anche se ha gia' un prestito suo.
        self.api.presta('111', self.gioco.id)
        p = self.api.presta_a_nome(self.libro.id, '', self.mario.id, 'Admin')
        self.assertEqual(p['socio'], 'Mario Rossi')
        with self.assertRaises(UserError):
            self.api.presta_a_nome(self.libro.id, '', False, 'Admin')

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

    def test_catalogo_piu_tipi_insieme(self):
        filtri = {'sede_id': self.sede.id}
        ids = [b['id'] for b in self.api.catalogo(
            dict(filtri, categoria=['libro', 'gioco_da_tavolo']))['beni']]
        self.assertEqual(sorted(ids), sorted([self.libro.id, self.gioco.id]))
        ids = [b['id'] for b in self.api.catalogo(dict(filtri, categoria='libro'))['beni']]
        self.assertEqual(ids, [self.libro.id])

    def test_catalogo_prima_i_piu_presi(self):
        filtri = {'sede_id': self.sede.id}
        self.assertEqual(self.api.catalogo(filtri)['beni'][0]['id'], self.gioco.id)  # C < I
        prestito = self.api.presta('111', self.libro.id)
        self.api.restituisci('111', prestito['id'])
        self.assertEqual(self.libro.numero_prestiti, 1)
        self.assertEqual(self.api.catalogo(filtri)['beni'][0]['id'], self.libro.id)

    def test_admin_e_prestiti_aperti(self):
        self.assertFalse(self.api.socio_da_telegram('111')['admin'])
        self.mario.admin_miniapp = True
        self.assertTrue(self.api.socio_da_telegram('111')['admin'])
        prestito = self.api.presta('222', self.libro.id)
        record = self.env['crocevia.prestito'].browse(prestito['id'])
        record.data_restituzione_prevista = fields.Date.context_today(record) - timedelta(days=3)
        aperti = {p['id']: p for p in self.api.prestiti_aperti()}
        self.assertEqual(aperti[prestito['id']]['giorni_ritardo'], 3)
        self.assertEqual(aperti[prestito['id']]['socio'], 'Anna Bianchi')
        self.api.chiudi_prestito(prestito['id'], 'Admin')
        self.assertEqual(self.libro.stato_bene, 'disponibile')
        self.assertNotIn(prestito['id'], [p['id'] for p in self.api.prestiti_aperti()])

    def test_catalogo_ordini(self):
        filtri = {'sede_id': self.sede.id}
        titoli = lambda o: [b['titolo'] for b in self.api.catalogo(filtri, ordine=o)['beni']]
        self.assertEqual(titoli('titolo'), ['Carcassonne', 'Il nome della rosa'])
        self.assertEqual(titoli('recenti'), ['Carcassonne', 'Il nome della rosa'])
        self.api.presta('111', self.gioco.id)
        self.assertEqual(titoli('disponibili'), ['Il nome della rosa', 'Carcassonne'])
        # A caso: gli stessi beni dei filtri, nello stesso ordine per lo
        # stesso seme.
        casuale = lambda seme: [b['titolo'] for b in self.api.catalogo(filtri, ordine='casuale', seme=seme)['beni']]
        self.assertEqual(sorted(casuale(7)), ['Carcassonne', 'Il nome della rosa'])
        self.assertEqual(casuale(7), casuale(7))
        # Un ordine sconosciuto non passa: si torna al predefinito.
        self.assertEqual(len(titoli('name; drop table x')), 2)

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
        # Solo i nostri: nel database possono esserci altri prestiti scaduti.
        nostri = lambda: [p for p in self.api.scaduti() if p['id'] == prestito['id']]
        self.assertFalse(nostri())
        record = self.env['crocevia.prestito'].browse(prestito['id'])
        record.data_restituzione_prevista = fields.Date.context_today(record)
        scaduti = nostri()
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

    def test_riapri_prestito(self):
        prestito = self.api.presta('111', self.libro.id)
        self.api.restituisci('111', prestito['id'])
        dati = self.api.riapri_prestito(prestito['id'], 'Staff')
        self.assertEqual(dati['telegram_id'], '111')
        self.assertTrue(dati['riaperto'])
        # Premuto due volte: la seconda non riapre niente.
        self.assertFalse(self.api.riapri_prestito(prestito['id'], 'Staff')['riaperto'])
        self.assertEqual(self.libro.stato_bene, 'in_prestito')
        # Se intanto l'ha preso un altro, non si riapre il vecchio.
        self.api.restituisci('111', prestito['id'])
        self.api.presta('222', self.libro.id)
        with self.assertRaises(UserError):
            self.api.riapri_prestito(prestito['id'], 'Staff')

    def test_modifica_bene(self):
        genere = self.api.crea_genere('Gialli di prova')
        valori = self.api.bene_da_modificare(self.libro.id)
        self.assertEqual(valori['name'], 'Il nome della rosa')
        self.api.modifica_bene(self.libro.id, {
            'name': 'Il nome della rosa (ed. 1980)', 'autore': '',
            'genere_ids': [genere['id']], 'mancante': True,
        }, 'Admin')
        self.assertEqual(self.libro.name, 'Il nome della rosa (ed. 1980)')
        self.assertFalse(self.libro.autore)
        self.assertEqual(self.libro.genere_ids.ids, [genere['id']])
        self.assertEqual(self.libro.stato_bene, 'mancante')
        # Quello che non arriva resta com'era.
        self.assertTrue(self.libro.isbn)
        with self.assertRaises(UserError):
            self.api.modifica_bene(self.libro.id, {'name': ''}, 'Admin')

    def test_dati_e_cancellazione(self):
        dati = self.api.dati_personali('111')
        self.assertEqual(dati['nome'], 'Mario Rossi')
        self.assertFalse(self.api.dati_personali('999'))
        prestito = self.api.presta('111', self.libro.id)
        with self.assertRaises(UserError):
            self.api.cancella_dati('111')
        self.api.restituisci('111', prestito['id'])
        esito = self.api.cancella_dati('111')
        self.assertFalse(esito['provvisorio'])
        self.assertFalse(self.mario.telegram_id)
        self.assertTrue(self.mario.active)
        self.assertFalse(self.api.socio_da_telegram('111'))

    def test_cancellazione_provvisoria(self):
        prov = self.api.registra_provvisorio('888', 'Nuova', 'Persona', False)
        self.assertTrue(self.api.cancella_dati('888')['provvisorio'])
        scheda = self.env['res.partner'].with_context(active_test=False).browse(prov['id'])
        self.assertFalse(scheda.active)
        self.assertFalse(scheda.is_socio)

    def test_isbn_a_10_e_13_cifre(self):
        # 88-452-0612-2 e 978-88-452-0612-2: stesso libro, cifre di
        # controllo diverse.
        libro = self.env['crocevia.bene'].create({
            'name': 'Il piccolo principe', 'categoria': 'libro',
            'sede_id': self.sede.id, 'isbn': '88-452-0612-2'})
        trovati = self.api.catalogo({'testo': '9788845206122'}, 0, 10, False)['beni']
        self.assertIn(libro.id, [b['id'] for b in trovati])

    def test_in_scadenza(self):
        prestito = self.api.presta('111', self.libro.id)
        record = self.env['crocevia.prestito'].browse(prestito['id'])
        record.data_restituzione_prevista = fields.Date.context_today(record) + timedelta(days=3)
        ids = [p['id'] for p in self.api.in_scadenza(3)]
        self.assertIn(prestito['id'], ids)
        self.assertNotIn(prestito['id'], [p['id'] for p in self.api.in_scadenza(2)])

    def test_pulisci_respinti(self):
        Partner = self.env['res.partner'].with_context(active_test=False)
        vecchio = fields.Date.context_today(self.mario) - timedelta(days=400)
        senza = self.api.registra_provvisorio('901', 'Senza', 'Prestiti', False)
        con = self.api.registra_provvisorio('902', 'Con', 'Prestiti', False)
        prestito = self.api.presta('902', self.gioco.id)
        self.api.restituisci('902', prestito['id'])
        recente = self.api.registra_provvisorio('903', 'Appena', 'Respintə', False)
        for p in (senza, con, recente):
            self.api.rifiuta_provvisorio(p['id'], 'Direttivo')
        Partner.browse([senza['id'], con['id']]).write({'miniapp_respinto_il': vecchio})
        self.env['crocevia.miniapp']._pulisci_respinti()
        self.assertFalse(Partner.browse(senza['id']).exists())
        anonima = Partner.browse(con['id'])
        self.assertTrue(anonima.exists())
        self.assertTrue(anonima.name.startswith('Ex utente app'))
        self.assertEqual(Partner.browse(recente['id']).name, 'Appena Respintə')

    def _valori_iscrizione(self, **altro):
        valori = {
            'nome': 'Giulia', 'cognome': 'Nuova', 'data_nascita': '1995-04-12',
            'luogo_nascita': 'Barletta', 'codice_fiscale': 'nvogli95d52a669x',
            'email': 'giulia@example.org', 'indirizzo': 'Via Prova 1',
            'cap': '76121', 'citta': 'Barletta', 'provincia': 'bt',
        }
        valori.update(altro)
        return valori

    def test_tesseramento_dalla_miniapp(self):
        self.assertFalse(self.api.stato_iscrizione('4444')['richiesta'])
        with self.assertRaises(UserError):
            self.api.richiedi_iscrizione('4444', self._valori_iscrizione(codice_fiscale='corto'))
        r = self.api.richiedi_iscrizione('4444', self._valori_iscrizione())
        # Una sola richiesta aperta per Telegram.
        self.assertEqual(self.api.richiedi_iscrizione('4444', self._valori_iscrizione())['id'], r['id'])
        self.assertEqual(self.api.stato_iscrizione('4444')['richiesta']['id'], r['id'])
        # Chi ha gia' una scheda non chiede il tesseramento.
        with self.assertRaises(UserError):
            self.api.richiedi_iscrizione('111', self._valori_iscrizione())
        socio = self.api.approva_iscrizione(r['id'], 'contanti', 'Direttivo')
        self.assertTrue(socio['numero_socio'])
        self.assertEqual(self.api.socio_da_telegram('4444')['id'], socio['id'])
        tessera = self.api.tessera('4444')
        self.assertTrue(tessera['tesserato'])
        self.assertEqual(len(tessera['ricevute']), 1)
        self.assertEqual(tessera['spese'][0]['quante'], 1)
        self.assertEqual(tessera['importi']['tesseramento'], tessera['quota'])
        self.assertEqual(tessera['mensilita'], [fields.Date.context_today(self.mario).strftime('%Y-%m')])
        with self.assertRaises(UserError):
            self.api.approva_iscrizione(r['id'], 'contanti', 'Direttivo')
        self.assertNotIn('4444', [s['telegram_id'] for s in self.api.da_rinnovare()])
        self.assertIn('111', [s['telegram_id'] for s in self.api.da_rinnovare()])

    def test_rifiuta_iscrizione(self):
        r = self.api.richiedi_iscrizione('5555', self._valori_iscrizione())
        self.assertEqual(self.api.rifiuta_iscrizione(r['id'], 'Direttivo')['telegram_id'], '5555')
        self.assertFalse(self.api.stato_iscrizione('5555')['richiesta'])
        self.assertFalse(self.api.socio_da_telegram('5555'))

    def test_ricevuta_solo_propria(self):
        Ricevuta = self.env['crocevia.ricevuta']
        mia = Ricevuta.create({'partner_id': self.mario.id, 'data': fields.Date.today(),
                               'tipo': 'obolo_giornaliero', 'importo': 2, 'metodo': 'contanti'})
        with self.assertRaises(UserError):
            self.api.ricevuta_pdf('222', mia.id)
        self.assertEqual([x['id'] for x in self.api.tessera('111')['ricevute']], [mia.id])
