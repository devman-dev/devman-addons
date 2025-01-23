from odoo import fields, models


class BankMoveImported(models.Model):
    _name = 'bank.move.imported'
    _description = 'Bank Move Imported'
    
    date = fields.Date(stirng='Fecha')
    bank_id = fields.Many2one('account.bank.pagoflex', string='Banco')
    file = fields.Binary(string='Archivo')
    comment = fields.Text(string='Comentario')
    amount = fields.Char(string='Col Monto')
    origin_account = fields.Char(string='Col Cuenta Origen')
    origin_cuit = fields.Char(string='Col Cuit Origen')
    origin_cvu = fields.Char(string='Col Cvu Origen')
    bank_commission_entry = fields.Char(string='Col Comision Banco Entrada')
    bank_commission_exit = fields.Char(string='Col Comision Banco Salida')