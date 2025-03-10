from odoo import fields, api, models

class AccountBankPagoFlex(models.Model):
    _name = 'account.bank.pagoflex'
    
    bank_id = fields.Many2one('res.bank', string='Banco', required=True)
    name = fields.Char(string='Nombre')
    cuit = fields.Char(string='CUIT')
    alias = fields.Char(string='Alias')
    cvu = fields.Char(string='CVU')
    cbu = fields.Char(string='CBU')
    commission_app = fields.Float('Comision de la app')