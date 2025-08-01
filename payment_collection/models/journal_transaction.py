from odoo import fields, models, api


class AccountPayment(models.Model):
    _name = 'journal.transaction'

    _rec_name = 'name'

    journal_id = fields.Many2one('account.journal')
    name = fields.Char('Nombre')