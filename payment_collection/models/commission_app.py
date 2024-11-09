from odoo import fields, models
import datetime

class CommissionApp(models.Model):
    _name = 'commission.app'
    _order = "date desc"
    
    date = fields.Date(default=datetime.datetime.now(), string='Fecha')
    commission_rate = fields.Float(string='Comisión')