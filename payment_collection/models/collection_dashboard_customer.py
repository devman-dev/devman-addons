from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime as dt


class CollectionDashboardCustomer(models.Model):
    _name = 'collection.dashboard.customer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    customer = fields.Many2one('res.partner', string='Cliente', domain="[('check_origin_account','!=', True)]", tracking=True)
    customer_real_balance = fields.Float(string='Saldo Real App', tracking=True)
    customer_available_balance = fields.Float(string='Saldo Disponible', tracking=True)
    collection_balance = fields.Float(string='Saldo Total Cliente', tracking=True)
    last_operation_date = fields.Date(string='Fecha de ultima operación', tracking=True)
    commission_balance = fields.Float(string='Saldo de Comisión', tracking=True)
    commission_app_rate = fields.Float(string='Comi. App (%)', tracking=True, digits=(16, 3))
    commission_app_amount = fields.Float(string='Monto App', tracking=True)
    manual_data = fields.Boolean(string='Data Manual', default=True, tracking=True)
    
    @api.model
    def update_available_balance(self):
        dashboard_customers = self.env['collection.dashboard.customer'].search([])
        today_date = dt.datetime.now().date()
        days_ago = dt.timedelta(days=2)
        for d in dashboard_customers:
            ct = self.env['collection.transaction'].sudo().search([('customer', '=', d.customer.id), ('date', '<=', today_date - days_ago)])
            if ct:
                d.sudo().customer_available_balance = 0
            for c in ct:
                d.sudo().customer_available_balance += c.amount
                

    def recalculate_total_recs(self, partner_id=False):
        dict_list = []
        # group = self.env.ref('payment_collection.groups_payment_collection_admin')
        # if group.id not in self.env.user.groups_id.ids:
        #     raise UserError('Esta función solo puede ser ejecutada por usuarios con permiso de administrador.')
        if not partner_id:
            all_recs = self.env['res.partner'].sudo().search([('check_origin_account', '=', False)])
        else:
            all_recs = self.env['res.partner'].sudo().search([('id', '=', partner_id)])
        today_date = dt.datetime.now().date()
        days_ago = dt.timedelta(days=2)
        
        
        result_collection_balance = 0
        for rec in all_recs:
            # Si no existe el contacto en collection.transaction se va
            if not self.env['collection.transaction'].search([('customer', '=', rec.id)]):
                continue
            
            # Busco el saldo disponible
            total_available = self.env['collection.transaction'].sudo().search([
                ('customer', '=', rec.id),
                ('date', '<=', today_date - days_ago),
                ('collection_trans_type', '=', 'movimiento_recaudacion')
            ])
            
            # Busco el total de recaudaciones
            total_recaudation = self.env['collection.transaction'].sudo().search([
                ('customer', '=', rec.id),
                # ('is_commission', '=', False),
                ('collection_trans_type', '=', 'movimiento_recaudacion'),
                '|',
                ('operation.name', 'not ilike', 'SALDO INICIAL'),
                ('service.services.name', 'not ilike', 'SALDO INICIAL'),
            ])

            # Busco el total de las recaudaciones con el saldo inicial
            total_recaudation_initial = self.env['collection.transaction'].sudo().search([
                ('customer', '=', rec.id),
                # ('is_commission', '=', False),
                ('collection_trans_type', '=', 'movimiento_recaudacion'),
            ])

            # Busco el total de los retiros
            total_withdrawal = self.env['collection.transaction'].sudo().search([
                ('customer', '=', rec.id), ('collection_trans_type', '=', 'retiro')
            ])

            # Busco el dashboard del cliente
            dashboard = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.id)])
            if not total_recaudation and not total_withdrawal and not total_available:
                continue
            
            # Establezco las variables
            total_amount_recau = 0
            total_amount_recau_initial = 0
            total_amount_withdr = 0
            total_amount_available = 0
            total_amount_app = 0
            total_amount_recau_no_commi = 0
            total_app_rate = 0
            total_commi_amount = 0
            
            """
            En estos dos montos: total_amount_recau, 
                                 total_amount_recau_initial -> (Aca viene con el saldo inicial)
            
            Vienen en negativo las comisiones, entonces ya se le restan
            y vienen en positivo las comisiones de los retiros y estas ya se suman -> esto es plata que se le suma a pablo (Saldo App)
            
            Ya vienen en estos datos porque las comisiones se guardan como movimiento_recaudacion
            independientemente si proviene de un retiro o una acreditacion
            """
            
            # Sumarizo los montos
            total_amount_recau = sum([c.amount for c in total_recaudation])
            # total_amount_recau_without_commi = sum([c.amount for c in total_recaudation if c.amount > 0])
            total_amount_recau_initial = sum([c.amount for c in total_recaudation_initial])
            
            total_amount_withdr = sum([c.amount for c in total_withdrawal])
            total_amount_available = sum([c.amount for c in total_available if not (c.is_commission and c.amount > 0) or not c.is_commission])
            total_amount_app = sum([c.commission_app_amount for c in total_recaudation])
            total_amount_recau_no_commi = [c.amount for c in total_recaudation if c.amount > 0]
            if not len(total_amount_recau_no_commi) == 0:
                total_app_rate = sum([c.commission_app_rate for c in total_recaudation]) / len(total_amount_recau_no_commi)
            else:
                total_app_rate = sum([c.commission_app_rate for c in total_recaudation])
            total_commi_amount = sum([c.amount for c in total_recaudation if c.is_commission])
            total_amount_recau_no_commi = sum(total_amount_recau_no_commi)

            """
            Saldo App = Total Recaudaciones - Total Comisiones App - Total Retiros
            Saldo Disponible = Total Disponible - Retiros - Total Comisiones
            Saldo Total Cliente = Total Recaudaciones - Total Comisiones - Total Retiros
            """
            
            
            #Saldo App
            result_customer_real_balance = total_amount_recau_no_commi - total_amount_app - abs(total_amount_withdr)
            
            #Saldo Disponible
            result_customer_available_balance = total_amount_available - abs(total_amount_withdr)
            
            #Saldo Total Cliente
            result_collection_balance = total_amount_recau_initial - abs(total_amount_withdr)
            
            dict_dashboard = {
                'customer': rec.id,
                'customer_real_balance': result_customer_real_balance,
                'customer_available_balance': result_customer_available_balance,
                'collection_balance': result_collection_balance,
                'commission_balance': total_commi_amount,
                'commission_app_rate': total_app_rate,
                'commission_app_amount': total_amount_app,
                'last_operation_date': dashboard.last_operation_date,
            }
            dict_list.append((0, 0, dict_dashboard))
        if partner_id:
            return result_collection_balance
        else:
            return {
                'name': 'Recálculo de Totales del Dashboard',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'recalculate.button.wiz',
                'type': 'ir.actions.act_window',
                'context': {'default_all_customer_dash': dict_list},
                'target': 'new',
            }