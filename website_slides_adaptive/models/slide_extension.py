from odoo import models, fields

class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    nivel_dificultad = fields.Selection([
        ('basico', 'Básico'),
        ('intermedio', 'Intermedio'),
        ('avanzado', 'Avanzado')
    ], string='Nivel de Dificultad', default='basico')
