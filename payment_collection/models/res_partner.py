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