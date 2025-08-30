from odoo import models, fields

class CasinoGameBank(models.Model):
    _name = 'casino.game.bank'
    _description = 'Bank'
    _order = "id desc"

    partner_id = fields.Many2one('res.partner', string='Titular')
    account_number = fields.Char('Cuenta Bancaria')
    bank_name = fields.Char('Banco')
    account_type = fields.Char('Tipo de Cuenta')
    cbu = fields.Char('CBU')
    cuil = fields.Char('CUIL')
