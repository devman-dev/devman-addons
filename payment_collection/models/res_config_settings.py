from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    caja_journal_id = fields.Many2one(
        'account.journal',
        string="Diario de Caja para collection.transaction",
        config_parameter='payment_collection.caja_journal_id',
        domain="[('type', '=', 'cash')]")
