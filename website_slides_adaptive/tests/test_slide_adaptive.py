from odoo.tests.common import TransactionCase

class TestSlideAdaptive(TransactionCase):
    def test_create_ruta_aprendizaje(self):
        user = self.env.ref('base.user_demo')
        channel = self.env['slide.channel'].create({'name': 'Curso Test'})
        ruta = self.env['slide.ruta.aprendizaje'].create({
            'user_id': user.id,
            'channel_id': channel.id,
            'nivel_dificultad': 'basico',
        })
        self.assertTrue(ruta)
        self.assertEqual(ruta.user_id, user)
