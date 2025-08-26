import uuid

from odoo import fields, models


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

    def _deposit_payments_fields(self):
        return [
            "date",
            "memo",
            "amount",
            "payment_total",
            "currency_id",
            "state",
        ]

    def get_deposit_payments(self):
        AccountPayment = self.env["account.payment"].sudo()
        self_sudo = self.sudo()
        domain = [
            ("payment_type", "=", "inbound"),
            ("state", "in", ("in_process", "paid")),
            ("partner_id", "=", self_sudo.id),
            ("move_id", "!=", False)
        ]
        return AccountPayment.search_read(domain, self._deposit_payments_fields())