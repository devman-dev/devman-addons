# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    commission = fields.Float(
        string='Commission (%)',
        digits=(16, 2),
        help='Commission percentage for this product'
    )
