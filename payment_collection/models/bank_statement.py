from odoo import models, fields, api

class BankStatement(models.Model):
    _name = 'bank.statement'
    _description = 'Bank Statement'

    date = fields.Date(string='Transaction Date', required=True)
    amount = fields.Float(string='Amount', required=True)
    titular = fields.Char(string='Account Holder', required=True)
    cuit = fields.Char(string='CUIT', required=True)
    bank = fields.Char(string='Bank', required=True)
    cvu = fields.Char(string='CVU', required=True)
    cbu = fields.Char(string='CBU', required=True)
    alias = fields.Char(string='Alias', required=False)
    id_coelsa = fields.Char(string='Coelsa ID', required=False)
    reference = fields.Char(string='Reference', help='Additional reference for the statement')
