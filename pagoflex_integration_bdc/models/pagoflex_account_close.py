from odoo import models, fields

class PagoflexAccountClose(models.Model):
    _name = 'pagoflex.account.close'
    _description = 'Solicitud de cierre de cuenta Pagoflex/Sivep'

    name = fields.Char(string='Nombre', required=True)
    email = fields.Char(string='Email', required=True)
    app = fields.Selection([
        ('sivep', 'Sivep'),
        ('pagoflex', 'Pagoflex')
    ], string='App', required=True)
    reason = fields.Text(string='Motivo', required=True)
