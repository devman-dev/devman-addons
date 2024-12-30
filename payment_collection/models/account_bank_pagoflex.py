from odoo import fields, api, models

class AccountBankPagoFlex(models.Model):
    _name = 'account.bank.pagoflex'
    
    
    name = fields.Char(string='Nombre', required=True)
    cuit = fields.Char(string='CUIT', required=True)
    alias = fields.Char(string='Alias', required=True)
    cvu = fields.Char(string='CVU', required=True)
    cbu = fields.Char(string='CBU', required=True)
    