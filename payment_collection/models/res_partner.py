from odoo import fields, models, api


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    check_origin_account = fields.Boolean('Cuenta Origen')
