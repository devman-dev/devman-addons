from odoo import models, fields


class PartnerPaymentMethodConfig(models.Model):
    _name = 'partner.payment.method.config'
    _description = 'Configuración de Métodos de Pago por Usuario'

    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, ondelete='cascade')
    payment_provider_id = fields.Many2one('payment.provider', string='Método de Pago', required=True, ondelete='cascade')

    for_deposit = fields.Boolean(string='Usar para Depósito', default=False)
    for_withdraw = fields.Boolean(string='Usar para Retiro', default=False)

    _sql_constraints = [
        ('partner_provider_unique', 'unique(partner_id, payment_provider_id)', 'Ya existe configuración para este método de pago y usuario.')
    ]
