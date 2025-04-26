##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MultiApprovalLine(models.Model):
    _name = "multi.approval.line"
    _description = "Approval Line"
    _order = "sequence"

    name = fields.Char(string="Title", required=True)
    user_id = fields.Many2one(string="User", comodel_name="res.users", required=True)
    sequence = fields.Integer()
    require_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
        ],
        string="Type of Approval",
        default="Required",
    )
    approval_id = fields.Many2one(string="Approval", comodel_name="multi.approval")
    state = fields.Selection(
        [
            ("Draft", "Draft"),
            ("Waiting for Approval", "Waiting for Approval"),
            ("Approved", "Approved"),
            ("Refused", "Refused"),
            ("Cancel", "Cancel"),
        ],
        default="Draft",
    )
    refused_reason = fields.Text()
    deadline = fields.Date()

    # 13.0.1.1
    def set_approved(self):
        self.ensure_one()
        self.state = "Approved"

    def set_refused(self, reason=""):
        self.ensure_one()
        self.write({"state": "Refused", "refused_reason": reason})
