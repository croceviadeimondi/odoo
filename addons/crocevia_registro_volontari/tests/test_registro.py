from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..utils.verifica_pades import verifica_pdf_firmato


@tagged('post_install', '-at_install')
class TestRegistroVolontari(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Isc = cls.env['crocevia.registro.iscrizione']
        cls.Vid = cls.env['crocevia.registro.vidimazione']
        # Vidimazione fittizia recente: sblocca il gate art. 2215-bis per
        # poter creare piu' iscrizioni nei test (la verifica firma reale
        # e' testata a parte / manualmente).
        cls.Vid.create({
            'stato': 'firmato_verificato',
            'firma_valida': True,
            'marca_temporale_data': fields.Datetime.now(),
            'firmatario_nome': 'Test',
        })

    def _crea_iscrizione(self, cf, nome='Mario', cognome='Rossi'):
        partner = self.env['res.partner'].create({
            'name': '%s %s' % (nome, cognome)})
        return self.Isc.create({
            'partner_id': partner.id,
            'nome': nome, 'cognome': cognome, 'codice_fiscale': cf,
            'data_nascita': '1980-01-01', 'luogo_nascita': 'Barletta',
            'indirizzo_residenza': 'Via Roma 1', 'cap_residenza': '76121',
            'citta_residenza': 'Barletta', 'provincia_residenza': 'BT',
            'tipo': 'abituale',
            'data_inizio_attivita': fields.Date.today(),
            'attivita_svolta': 'Mansioni di test',
        })

    def test_hash_chain_e_congelamento(self):
        a = self._crea_iscrizione('RSSMRA80A01A662A')
        b = self._crea_iscrizione('VRDLGI85B02A662B', nome='Luigi', cognome='Verdi')
        self.assertEqual(a.stato_inalterabilita, 'bozza')

        n = self.Isc._congela_bozza_per_vidimazione()
        self.assertEqual(n, 2)
        a.invalidate_recordset()
        b.invalidate_recordset()
        self.assertEqual(a.stato_inalterabilita, 'vidimato')
        self.assertTrue(a.hash_record)
        self.assertTrue(b.hash_precedente)
        # La catena dev'essere integra.
        self.Isc.action_verifica_catena()

    def test_manomissione_rilevata(self):
        a = self._crea_iscrizione('BNCstr80A01A662C', nome='Anna', cognome='Bianchi')
        self.Isc._congela_bozza_per_vidimazione()
        # Assicura che l'hash del congelamento sia scritto in DB prima della
        # manomissione grezza (altrimenti un flush ORM successivo la annulla).
        self.env.flush_all()
        # Manomissione diretta in DB (bypassa l'ORM/write-once).
        self.env.cr.execute(
            "UPDATE crocevia_registro_iscrizione SET hash_record=%s WHERE id=%s",
            ('00' * 32, a.id))
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            self.Isc.action_verifica_catena()

    def test_write_once_dopo_vidimazione(self):
        a = self._crea_iscrizione('CCCMRA80A01A662D')
        self.Isc._congela_bozza_per_vidimazione()
        a.invalidate_recordset()
        with self.assertRaises(UserError):
            a.write({'nome': 'Cambiato'})
        with self.assertRaises(UserError):
            a.unlink()

    def test_cf_univoco(self):
        self._crea_iscrizione('DDDMRA80A01A662E')
        with self.assertRaises(ValidationError):
            self._crea_iscrizione('DDDMRA80A01A662E', nome='Altro')

    def test_verificatore_pdf_non_valido(self):
        # Bytes spazzatura -> nessuna firma / errore, non valida.
        esito = verifica_pdf_firmato(b'questo non e un pdf')
        self.assertFalse(esito['valida'])
        self.assertTrue(esito['dettagli'])

    def test_verificatore_pdf_senza_firma(self):
        pdf = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
               b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
               b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n'
               b'xref\n0 4\n0000000000 65535 f \n'
               b'trailer<</Root 1 0 R/Size 4>>\nstartxref\n0\n%%EOF')
        esito = verifica_pdf_firmato(pdf)
        self.assertFalse(esito['valida'])
