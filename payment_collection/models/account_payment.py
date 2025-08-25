from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    check_origin_collection = fields.Boolean(string='Origen Recaudación')
    id_transaction = fields.Integer(string='Id')

    @api.model
    def create(self, vals):
        payment = super().create(vals)

        #if vals['check_origin_collection']:
        if vals.get('check_origin_collection'):

            transaction = self.env['collection.transaction'].sudo().search([('id','=', vals['id_transaction'])])
            if transaction:
                transaction.payment_id = payment.id

        return payment
