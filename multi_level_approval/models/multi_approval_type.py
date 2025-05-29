##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MultiApprovalType(models.Model):
    _name = "multi.approval.type"
    _description = "Approval Type"

    name = fields.Char(required=True)
    description = fields.Char()
    image = fields.Binary(attachment=True)
    active = fields.Boolean(default=True, readonly=False)
    mail_notification = fields.Boolean()
    mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Template for the request",
        help="Let it empty if you want to send the description of the request",
    )
    approve_mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Template of `Approved` Case",
        help="Let it empty if don't want notify",
    )
    refuse_mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Template of `Refused` Case",
        help="Let it empty if don't want notify",
    )
    line_ids = fields.One2many(
        "multi.approval.type.line", "type_id", string="Approvers", required=True
    )
    approval_minimum = fields.Integer(
        string="Minimum Approvers", compute="_compute_approval_minimum", readonly=True
    )
    document_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
        ],
        default="Optional",
    )
    contact_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    date_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    period_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    item_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    multi_items_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    quantity_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    amount_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    reference_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    payment_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    location_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
            ("None", "None"),
        ],
        default="None",
    )
    submitted_nb = fields.Integer(
        string="To Review", compute="_compute_submitted_request"
    )
    activity_notification = fields.Boolean()

    def _compute_submitted_request(self):
        for r in self:
            r.submitted_nb = self.env["multi.approval"].search_count(
                [("type_id", "=", r.id), ("state", "=", "Submitted")]
            )

    @api.depends("line_ids")
    def _compute_approval_minimum(self):
        for rec in self:
            required_lines = rec.line_ids.filtered(
                lambda _l: _l.require_opt == "Required"
            )
            rec.approval_minimum = len(required_lines)

    def create_request(self):
        self.ensure_one()
        view_id = self.env.ref("multi_level_approval.multi_approval_view_form", False)
        return {
            "name": self.env._("New Request"),
            "view_mode": "form",
            "res_model": "multi.approval",
            "view_id": view_id and view_id.id or False,
            "type": "ir.actions.act_window",
            "context": {
                "default_type_id": self.id,
            },
        }

    def open_submitted_request(self):
        self.ensure_one()
        return {
            "name": self.env._("Submitted Requests"),
            "view_mode": "list,form",
            "res_model": "multi.approval",
            "view_id": False,
            "type": "ir.actions.act_window",
            "domain": [("type_id", "=", self.id), ("state", "=", "Submitted")],
            "context": {
                "default_type_id": self.id,
            },
        }
