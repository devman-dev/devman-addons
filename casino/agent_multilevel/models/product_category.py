# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    commission = fields.Float(
        string='Commission (%)',
        digits=(16, 2),
        help='Commission percentage for this public category'
    )
    
    product_count = fields.Integer(
        string='Products',
        compute='_compute_product_count'
    )

    @api.depends('commission')
    def _compute_product_count(self):
        Product = self.env['product.template']
        for category in self:
            category.product_count = Product.search_count([('public_categ_ids', 'in', category.id)])

    def action_update_products_commission(self):
        """Open wizard to propagate commission manually"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agent_multilevel.public.category.commission.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_category_id': self.id,
                'default_commission': self.commission,
                'default_only_games': 'is_game' in self.env['product.template']._fields,
            }
        }
