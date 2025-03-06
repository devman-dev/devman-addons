from odoo import fields, models, api



class FilterCollectionMovementWiz(models.TransientModel):
    _name = 'filter.collection.movement'

    customer_code = fields.Char(string='Código Cliente')
    customer = fields.Many2one('res.partner', string='Cliente', tracking=True, domain="[('check_origin_account','!=', True)]")
    service = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)
    operation = fields.Many2one('product.template', relation='operation', string='Operación', tracking=True)
    bank = fields.Many2one('res.bank', string='Banco')
    service_ids = fields.Many2many('collection.services.commission', string='Servicio', tracking=True)


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


    @api.onchange('customer_code')
    def _get_bank_accounts(self):
        for rec in self:
            if rec.customer_code:
                customer_code = rec.customer_code.zfill(5)
                service_id = self.env['collection.services.commission'].search([('customer.customer_code', '=', customer_code)])
                if not service_id:
                    rec.service_ids = False
                else:
                    rec.service_ids = service_id.ids
            else:
                rec.service_ids = False

