from odoo import fields, models


class CollectionCategory(models.Model):
    _name = 'collection.category'
    
    name = fields.Char(string='Nombre')