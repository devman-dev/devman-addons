# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo import api, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    casino_operation_type = fields.Selection([
        ('deposit', 'Depósito'),
        ('withdrawal', 'Retiro'),
        ('bet', 'Apuesta'),
        ('win', 'Ganancia'),
        ('adjustment', 'Ajuste'),
    ], string='Tipo de Operación Casino')

    @api.model_create_multi
    def create(self, vals_list):
        """
        Auto-publica los pagos en diarios de casino al crear.
        """
        records = super().create(vals_list)

        company = self.env.company
        casino_journals = company.casino_deposit_journal_id | company.casino_bet_transfer_journal_id

        for payment in records:
            if payment.state == 'draft' and payment.journal_id in casino_journals:
                payment.sudo().action_post()

        return records

    @api.model
    def action_open_casino_payments(self):
        """
        Abre la vista de pagos de casino filtrada por los journals configurados en la compañía.
        """
        company = self.env.company
        
        # Journals configurados para casino (custodia y operativo)
        casino_journals = company.casino_deposit_journal_id | company.casino_bet_transfer_journal_id
        casino_journal_ids = [jid for jid in casino_journals.ids if jid]

        # Dominio: pagos cuyo journal o destination_journal pertenezca a los diarios de casino
        if casino_journal_ids:
            domain = [('journal_id', 'in', casino_journal_ids)]
        else:
            # Si no hay diarios configurados, no mostrar nada para evitar ruido
            domain = [('id', '=', 0)]
        
        return {
            'name': 'Pagos de Casino',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'tree,form,pivot,graph',
            'domain': domain,
            'context': {
                'default_payment_type': 'inbound',
                'search_default_filter_posted': 1,
            },
        }


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def action_open_casino_moves(self):
        """
        Abre la vista de asientos de casino filtrados por journals y cuentas de casino.
        """
        company = self.env.company
        
        # Obtener journals y cuentas de casino
        casino_journals = company.casino_deposit_journal_id | company.casino_bet_transfer_journal_id
        casino_journal_ids = casino_journals.ids
        
        casino_accounts = company.casino_deposit_account_id | company.casino_bet_account_id
        casino_account_ids = casino_accounts.ids
        
        # Dominio para filtrar asientos que usen journals o cuentas de casino
        domain = [
            '|',
            ('journal_id', 'in', casino_journal_ids),
            ('line_ids.account_id', 'in', casino_account_ids),
        ]
        
        return {
            'name': 'Asientos de Casino',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'search_default_filter_posted': 1,
            },
        }
