from odoo import fields, models, api
import re
from odoo.exceptions import UserError
class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    check_origin_account = fields.Boolean('Cuenta Origen')
    customer_code = fields.Char('Código Cliente')

    def create(self, vals_list):
        if 'customer_code' not in vals_list:
            vals_list['customer_code'] = self.env['ir.sequence'].next_by_code('res.partner') or ('New')
            res = super().create(vals_list)
            res._insert_customer_code()
        return res

    def upload_customer_code(self):
        all_recs = self.env['res.partner'].search([('customer_code', '=', False)])
        for rec in all_recs:
            rec.customer_code = self.env['ir.sequence'].next_by_code('res.partner') or ('New')
            rec._insert_customer_code()
    
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
