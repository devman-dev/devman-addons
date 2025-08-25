from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    ignore_journal_checkbook_sequence = fields.Boolean(
        default=True,
        help="If enabled, it will ignore the Journal Sequence uded for checkbook.",
    )
