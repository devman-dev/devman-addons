from odoo import fields, models, api
import datetime

class CollectionDashboardCustomer(models.Model):
    _name = 'collection.dashboard.customer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    customer = fields.Many2one('res.partner', string='Cliente', domain="[('check_origin_account','!=', True)]", tracking=True)
    customer_real_balance = fields.Float(string='Saldo Real App', tracking=True)
    customer_available_balance = fields.Float(string='Saldo Disponible', tracking=True)
    collection_balance = fields.Float(string='Saldo Total Cliente', tracking=True)
    last_operation_date = fields.Date(string='Fecha de ultima operación', tracking=True)
    commission_balance = fields.Float(string='Saldo de Comisión', tracking=True)
    commission_app_rate = fields.Float(string='Comi. App (%)', tracking=True)
    commission_app_amount = fields.Float(string='Monto App', tracking=True)
    manual_data = fields.Boolean(string='Data Manual', default=True, tracking=True)
    
    @api.model
    def update_available_balance(self):
        dashboard_customers = self.env['collection.dashboard.customer'].search([])
        today_date = datetime.datetime.now().date()
        days_ago = datetime.timedelta(days=2)
        for d in dashboard_customers:
            ct = self.env['collection.transaction'].sudo().search([('customer', '=', d.customer.id), ('date', '<=', today_date - days_ago)])
            if ct:
                d.sudo().customer_available_balance = 0
            for c in ct:
                d.sudo().customer_available_balance += c.amount
                
