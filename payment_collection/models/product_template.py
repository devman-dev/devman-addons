from odoo import fields, models

class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'
    
    collection_type = fields.Selection([('service','Servicio'),('operation','Operación')], string='Tipo de Cobro')
    commission_default = fields.Float(string='Comisión Default')
    check_internal = fields.Boolean('Movimiento Interno')
    check_withdrawal = fields.Boolean('Retiro')
    check_accreditation = fields.Boolean('Acreditación')
