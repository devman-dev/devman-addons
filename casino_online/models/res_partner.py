import uuid

from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    daily_deposit_limit = fields.Float(string='Límite diario de depósito')
    weekly_deposit_limit = fields.Float(string='Límite semanal de depósito')
    monthly_deposit_limit = fields.Float(string='Límite mensual de depósito')
    
    
    account_number = fields.Char('Cuenta Bancaria')
    bank_name = fields.Char('Banco')
    account_type = fields.Char('Tipo de Cuenta')
    cbu = fields.Char('CBU')
    cuil = fields.Char('CUIL')
    nuevo_cbu = fields.Char('Nuevo CBU')
    token = fields.Char(string='Token', default=lambda self: str(uuid.uuid4()))
    nickname = fields.Char(string='Nickname')