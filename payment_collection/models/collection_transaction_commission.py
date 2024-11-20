from odoo import fields, models, api

from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import datetime

class CollectionTransactionCommission(models.Model):
    _name = 'collection.transaction.commission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'transaction_name'
    _order = "transaction_name, id"

    date = fields.Date(string='Fecha', tracking=True, default=datetime.datetime.now())
    transaction_name = fields.Char(string='N° Transaccion', tracking=True,)
    customer = fields.Many2one('res.partner', string='Cliente', tracking=True, domain="[('check_origin_account','!=', True)]")
    transaction_service = fields.Many2one('collection.services.commission', string='Servicio de Transacción', tracking=True,)
    transaction_operation = fields.Many2one('product.template', relation='operation', string='Operación de Transacción', tracking=True,)
    agent = fields.Many2one('res.partner', string='Agente', tracking=True, domain="[('check_origin_account','!=', True)]")
    commission_rate = fields.Float(string='Tasa de comisión', tracking=True,)
    operation_amount = fields.Float(string='Monto de Operación', tracking=True,)
    commission_amount = fields.Float(string='Monto de Comisión', tracking=True,)
    payment_state = fields.Selection([('debt', 'Deuda'), ('pay', 'Pagado'), ('partial_payment', 'Pago Parcial')], default='debt', string='Estado', tracking=True,)
    payment_amount = fields.Float(string='Pago', tracking=True,)
    payment_rest = fields.Float(string='Resto', tracking=True,)
    payment_date = fields.Datetime(string='Fecha de Pago', tracking=True,)
    check_view_fields = fields.Boolean('Crear linea en positivo')
    description = fields.Text('Descripción', tracking=True,)
    duplicate = fields.Boolean('Duplicado')
    previous_month = fields.Float('Mes Anterior')

    @api.model
    def create(self, vals):

        res = super(CollectionTransactionCommission, self).create(vals)

        message = ("Se ha creado la siguiente transaccion: %s.") % (str(vals['transaction_name']))

        res.message_post(body=message)

        return res

    def unlink(self):
        # Custom code before deletion
        for rec in self:
            if not rec.duplicate:
                domain = [('transaction_name','=',rec.transaction_name),('agent','=', rec.agent.id),('duplicate','=',True)]
                search_payments = self.env['collection.transaction.commission'].search(domain)
                for sp in search_payments:
                    sp.unlink()

        result = super(CollectionTransactionCommission, self).unlink()

        return result

    def open_payment_wiz(self):
        context = {}
        ids = []
        for rec in self:
            if rec.payment_state == 'pay':
                raise ValidationError('La transacción ya se encuentra en estado Pagado')
            ids.append(rec.id)
        context['collection_transaction'] = ids
        total_amount = [rec.commission_amount for rec in self]
        context['default_total_amount'] = sum(total_amount)
        return {
            'name': 'Pago',
            'view_type': 'form',
            'view_mode': 'form',
            'context': context,
            'res_model': 'payment.wiz',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def open_report_agent_wiz(self):
        return {
            'name': 'Reporte de agente',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'report.agent.wiz',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }




    @api.onchange('commission_amount')
    def create_negative_commission(self):
        for rec in self:
            value = rec.commission_amount * -1
            if rec.commission_amount >= 1 and not rec.check_view_fields:
                rec.commission_amount = value

            if rec.commission_amount < 0 and not rec.check_view_fields:
                rec.payment_state = False
                rec.duplicate = True
                rec.payment_date = datetime.datetime.now()

