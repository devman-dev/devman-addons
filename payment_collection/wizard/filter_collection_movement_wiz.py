from odoo import fields, models
from datetime import datetime


class FilterCollectionMovementWiz(models.TransientModel):
    _name = 'filter.collection.movement'

    customer_code = fields.Char(string='Código Cliente')
    customer = fields.Many2one('res.partner', string='Cliente', tracking=True, domain="[('check_origin_account','!=', True)]")
    service = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)
    operation = fields.Many2one('product.template', relation='operation', string='Operación', tracking=True)
    bank = fields.Many2one('res.bank')


    def show_collection(self):
        self.ensure_one()

        domain = []

        if self.customer:
            domain.append(('customer', '=', self.customer.id))
        if self.customer_code:
            domain.append(('customer.customer_code', '=', self.customer_code))
        if self.service:
            domain.append(('service', '=', self.service.id))
        if self.operation:
            domain.append(('operation', '=', self.operation.id))
        if self.bank:
            domain.append(('service.bank_id', '=', self.bank.id))

        movements_ids = self.env['collection.transaction'].sudo().search(domain)

        vista_id = self.env.ref('payment_collection.collection_transaction_view_tree').id

        return {
            'name': 'Filtrar',
            'view_mode': 'tree',
            'res_model': 'collection.transaction',
            'type': 'ir.actions.act_window',
            'views': [(vista_id, 'tree')],
            'target': 'current',
            'domain': [('id', 'in', movements_ids.ids)],
        }




