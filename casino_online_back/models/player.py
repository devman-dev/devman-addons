from odoo import models, fields

class CasinoPlayer(models.Model):
    _inherit = 'res.users'

    dni = fields.Char(string='DNI')
    cuit = fields.Char(string='CUIT')
    birth_date = fields.Date(string='Fecha de nacimiento')
    onboarding_state = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Enviado'),
        ('in_review', 'En Revisión'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado')
    ], string='Estado de Onboarding', default='draft')
    dni_front = fields.Binary(string='Frente DNI')
    dni_back = fields.Binary(string='Dorso DNI')
    selfie = fields.Binary(string='Selfie')
    video = fields.Binary(string='Video prueba de vida')
    # Compatibilidad con vistas/flows heredados que aún esperan `token`.
    token = fields.Char(related='signup_token', readonly=False)
    signup_token = fields.Char(string='Token de Registro')
    signup_type = fields.Char(string='Tipo de Registro')
    signup_expiration = fields.Datetime(string='Expiración del Token')
