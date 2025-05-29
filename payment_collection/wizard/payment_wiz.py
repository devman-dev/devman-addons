from odoo import fields, models
from datetime import datetime


class PaymentWiz(models.TransientModel):
    _name = 'payment.wiz'

    payment_type = fields.Selection([('complete', 'Pago Completo'), ('partial', 'Pago Parcial')], default='complete', string='Tipo de Pago')
    amount = fields.Float(string='Monto')
    total_amount = fields.Float(string='Monto Total')
    def confirm(self):
        records = self.env['collection.transaction.commission'].search([('id', 'in', self.env.context['collection_transaction'])])
        for r in records:
            r.sudo().write(
                {
                    'payment_state': 'pay',
                    'payment_date': datetime.now(),
                    'payment_amount': r.commission_amount,
                    'payment_rest': 0
                }
            )
            new_payment = { 'transaction_name': r.transaction_name,
                            'payment_state': 'pay',
                            'date': datetime.now(),
                            'agent': r.agent.id,
                            'payment_date': datetime.now(),
                            'payment_amount': 0,
                            'commission_amount': r.commission_amount * -1,
                            'payment_rest': 0,
                            'description': 'Comisión',
                            'duplicate': True,
                            }
            self.env['collection.transaction.commission'].sudo().create(new_payment)

