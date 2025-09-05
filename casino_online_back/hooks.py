from odoo import api, SUPERUSER_ID

def create_bet_limits_for_all_partners(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env['res.partner'].sudo()
    BetLimits = env['casino.game.bet.limits'].sudo()

    partners = Partner.search([])
    for partner in partners:
        BetLimits.get_or_create_for_partner(partner)
