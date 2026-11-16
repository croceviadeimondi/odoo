from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFoglio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.utente = cls.env.ref('crocevia_miniapp.user_foglio')
        cls.api = cls.env['crocevia.foglio'].with_user(cls.utente)
        cls.sede = cls.env['crocevia.sede'].create({'citta': 'Sede di prova'})
        Bene = cls.env['crocevia.bene']
        cls.libro = Bene.create({
            'name': 'Il nome della rosa', 'categoria': 'libro',
            'autore': 'Eco', 'sede_id': cls.sede.id})
        cls.gioco = Bene.create({
            'name': 'Carcassonne', 'categoria': 'gioco_da_tavolo',
            'sede_id': cls.sede.id})
        cls.socio = cls.env['res.partner'].create({
            'name': 'Zebedeo Quarzini', 'is_socio': True, 'stato_socio': 'attivo'})

    def _righe(self, **kw):
        righe = self.api.elenco(sede='sede di prova', **kw)
        intestazione = righe[0]
        return [dict(zip(intestazione, r)) for r in righe[1:]]

    def test_solo_libri_della_sede(self):
        righe = self._righe()
        self.assertEqual([r['Titolo'] for r in righe], ['Il nome della rosa'])
        self.assertEqual(righe[0]['Stato'], 'Disponibile')
        self.assertEqual(len(self._righe(categoria=False)), 2)

    def test_prestito_senza_nome(self):
        self.env['crocevia.prestito'].create({
            'bene_id': self.libro.id, 'partner_id': self.socio.id,
            'data_restituzione_prevista': '2099-01-31'})
        riga = self._righe()[0]
        self.assertEqual(riga['Stato'], 'In prestito')
        self.assertEqual(riga['Rientro previsto'], '2099-01-31')
        self.assertNotIn('Quarzini', str(self.api.elenco()))

    def test_solo_utente_foglio(self):
        interno = self.env['res.users'].create({
            'name': 'Un membro', 'login': 'membro_foglio',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['crocevia.foglio'].with_user(interno).elenco()

    def test_utente_foglio_non_legge_i_modelli(self):
        with self.assertRaises(AccessError):
            self.env['crocevia.bene'].with_user(self.utente).search([])
