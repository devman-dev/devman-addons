from odoo import fields, models

HTTP_METHODS = [
    ("GET", "GET"),
    ("POST", "POST"),
    ("PUT", "PUT"),
    ("PATCH", "PATCH"),
    ("DELETE", "DELETE"),
]

class BdcEndpoint(models.Model):
    _name = "bdc.endpoint"
    _description = "BDC API Endpoint"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code"

    active = fields.Boolean(default=True)
    code = fields.Char(required=True, tracking=True, help="Internal code to reference this endpoint from code.")
    name = fields.Char(required=True, tracking=True)
    method = fields.Selection(HTTP_METHODS, required=True, default="GET", tracking=True)
    path = fields.Char(required=True, tracking=True, help="Path relative to Base URL, e.g. /v1/payments")
    description = fields.Text()
    requires_auth = fields.Boolean(default=True)
    request_schema = fields.Text(help="Optional: JSON schema or example payload.")
    response_schema = fields.Text(help="Optional: JSON schema or example response.")

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, index=True)
    openapi_source = fields.Char(help="OpenAPI document URL used to import this endpoint (if applicable).")

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "Endpoint code must be unique per company."),
    ]
