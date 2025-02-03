from odoo import fields, models, api
import re
from odoo.exceptions import UserError
class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    check_origin_account = fields.Boolean('Cuenta Origen')
    customer_code = fields.Char('Código Cliente')
    
    @api.constrains('customer_code', 'name')
    def _insert_customer_code(self):
        """ Agrega o actualiza el código de cliente en el display_name. """
        for rec in self:
            if not self.env.context.get('pass_constrain', False):
                if rec.customer_code:
                    pattern = r"\[\d+\]"
                    base_name = re.sub(pattern, "", rec.name).strip()
                    same_code = self.env['res.partner'].search([('customer_code', '=', rec.customer_code.upper()),('id', '!=', rec.id)])
                    if same_code:
                        raise UserError('El código de cliente ya existe en otro registro.')
                    
                    rec.with_context(pass_constrain=True).write({'name': f'{base_name} [{rec.customer_code.upper()}]'})  
                else:
                    pattern = r"\[\d+\]"
                    base_name = re.sub(pattern, "", rec.name).strip()
                    rec.with_context(pass_constrain=True).name = base_name