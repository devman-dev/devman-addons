from odoo import fields, models, api


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    cbu_destination = fields.Char('CBU Destino')
    cvu_destination = fields.Char('CVU Destino')
    alias_destination = fields.Char('Alias Destino')
    name_account_destination = fields.Char('Nombre Cuenta Destino')
    cuit_destination = fields.Char('CUIT Destino')
    
    cbu_account_source = fields.Char('CBU Origen')
    cvu_account_source = fields.Char('CVU Origen')
    alias_account_source = fields.Char('Alias Origen')
    cuit_account_source = fields.Char('CUIT Origen')
    name_account_source = fields.Char('Nombre Cuenta Origen')

    check_origin_account = fields.Boolean('Cuenta Origen')

    customer_services_ids = fields.One2many('customer.services','customer_services_id')



class CustomerServices(models.Model):
    _name = "customer.services"
    _rec_name = "name_account"

    cbu = fields.Char('CBU')
    cvu = fields.Char('CVU')
    alias = fields.Char('Alias')
    name_account = fields.Char('Nombre Cuenta')
    cuit = fields.Char('CUIT')
    service = fields.Many2one('product.template', domain="[('collection_type', '=', 'service')]", string="Servicio")
    customer_services_id = fields.Many2one('res.partner')