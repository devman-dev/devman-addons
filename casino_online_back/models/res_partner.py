from odoo import models, api

class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        BetLimits = self.env['casino.game.bet.limits'].sudo()
        default_company = self.env.company or self.env['res.company'].sudo().search([], limit=1)

        for partner in partners:
            BetLimits.get_or_create_for_partner(partner, company=default_company)

        return partners
