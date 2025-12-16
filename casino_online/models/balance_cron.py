from odoo import models, api

class BalanceGameCron(models.Model):
    _inherit = 'res.partner'

    # @api.model
    # def cron_update_balance_game(self):
    #     # Buscar todos los partners con token
    #     partners = self.env['res.partner'].sudo().search([('token', '!=', False)])
    #     for partner in partners:
    #         company = partner.company_id or self.env.company
    #         domain = [
    #             ('company_id', '=', company.id),
    #             ('partner_id', '=', partner.id),
    #             ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
    #             ('parent_state', 'in', ['draft', 'posted']),
    #         ]
    #         lines = self.env['account.move.line'].sudo().search(domain)
    #         total = sum(
    #             float((l.amount_signed if l.amount_signed is not None else l.balance) or 0.0)
    #             for l in lines
    #         )
    #         partner.balance_game = round(total, 2)
