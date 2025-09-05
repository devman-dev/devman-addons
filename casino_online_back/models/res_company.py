# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    bet_msg_daily   = fields.Char(string="Mensaje límite diario",   default="")
    bet_msg_weekly  = fields.Char(string="Mensaje límite semanal",  default="")
    bet_msg_monthly = fields.Char(string="Mensaje límite mensual",  default="")
