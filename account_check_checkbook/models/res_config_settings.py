from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ignore_journal_checkbook_sequence = fields.Boolean(
        related="company_id.ignore_journal_checkbook_sequence",
        readonly=False,
        help="If enabled, it will ignore the Journal Sequence uded for checkbook.",
    )
    
    
    
    
