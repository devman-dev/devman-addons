from odoo import fields, models


class ListNmaeAccount(models.TransientModel):
    _name = 'list.name.account'

    name = fields.Char()
