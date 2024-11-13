from odoo import fields, models, api


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    cbu_destination = fields.Char('CBU')
    cvu_destination = fields.Char('CVU')
    alias_destination = fields.Char('Alias')
    name_account_destination = fields.Char('Nombre de Cuenta')
