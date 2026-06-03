from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLibriSociali(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vid = cls.env['crocevia.libro.vidimazione']
        cls.Verbale = cls.env['crocevia.verbale']

    def test_records_snapshot_verbali_esclude_informali(self):
        self.Verbale.create({'name': 'Assemblea ordinaria', 'tipo': 'assemblea_soci',
                             'data': fields.Date.today()})
        self.Verbale.create({'name': 'Chiacchierata', 'tipo': 'resoconto_informale',
                             'data': fields.Date.today()})
        v = self.Vid.create({'tipo_libro': 'verbali_assemblea'})
        nomi = v._records_snapshot().mapped('name')
        self.assertIn('Assemblea ordinaria', nomi)
        self.assertNotIn('Chiacchierata', nomi)

    def test_genera_snapshot_soci(self):
        p = self.env['res.partner'].create({
            'name': 'Socia Test', 'is_socio': True, 'numero_socio': '9001'})
        v = self.Vid.create({'tipo_libro': 'soci'})
        v.action_genera_snapshot()
        self.assertEqual(v.stato, 'pdf_generato')
        self.assertTrue(v.pdf_unsigned_hash)
        self.assertTrue(v.pdf_unsigned)
        self.assertGreaterEqual(v.record_count, 1)
        self.assertIn(p, v._records_snapshot())

    def test_write_once_dopo_chiusura(self):
        v = self.Vid.create({
            'tipo_libro': 'soci', 'stato': 'firmato_verificato',
            'firma_valida': True, 'marca_temporale_data': fields.Datetime.now()})
        with self.assertRaises(UserError):
            v.write({'data_snapshot': fields.Datetime.now()})
        with self.assertRaises(UserError):
            v.unlink()
