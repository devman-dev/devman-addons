# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PublicCategoryCommissionWizard(models.TransientModel):
    _name = 'casino_agentes.public.category.commission.wizard'
    _description = 'Propagate commission from public category'

    category_id = fields.Many2one('product.public.category', string='Public Category', required=True)
    commission = fields.Float(string='Commission (%)', digits=(16, 2), required=True)
    apply_to_children = fields.Boolean(string='Include child categories', default=False)
    only_games = fields.Boolean(string='Only games (if available)', default=True,
                                help='If the field is_game exists on product, the filter will be applied.')
    overwrite_existing = fields.Boolean(string='Overwrite existing commission', default=True)

    def action_apply(self):
        self.ensure_one()
        Product = self.env['product.template']

        # Build categories set
        if self.apply_to_children:
            cats = self.category_id.search([('id', 'child_of', self.category_id.id)])
            cat_ids = cats.ids
        else:
            cat_ids = [self.category_id.id]

        domain = [('public_categ_ids', 'in', cat_ids)]

        # Filter only games when applicable
        if self.only_games and 'is_game' in Product._fields:
            domain.append(('is_game', '=', True))

        if not self.overwrite_existing:
            domain += ['|', ('commission', '=', False), ('commission', '=', 0)]

        products = Product.search(domain)
        products.write({'commission': self.commission})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%s products updated with %.2f%% commission.') % (len(products), self.commission),
                'type': 'success',
                'sticky': False,
            }
        }
