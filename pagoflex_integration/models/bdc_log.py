from odoo import fields, models

class BdcRequestLog(models.Model):
    _name = "bdc.request.log"
    _description = "BDC API Request Log"
    _order = "create_date desc"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, index=True)

    endpoint_id = fields.Many2one("bdc.endpoint", ondelete="set null")
    endpoint_code = fields.Char(index=True)
    method = fields.Char()
    url = fields.Char()
    status_code = fields.Integer()
    duration_ms = fields.Integer()

    request_headers = fields.Text()
    request_params = fields.Text()
    request_body = fields.Text()

    response_headers = fields.Text()
    response_body = fields.Text()

    error = fields.Text()
