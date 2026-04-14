from odoo import fields, models


class CasinoApiAuditEvent(models.Model):
    _name = "casino.api.audit.event"
    _description = "Casino API Audit Event"
    _order = "id desc"

    operation_id = fields.Many2one("casino.api.operation", required=True, ondelete="cascade", index=True)
    trace_id = fields.Char(index=True)
    event_type = fields.Char(required=True, index=True)
    event_ts = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    http_status = fields.Integer()
    message = fields.Char()
    payload_json = fields.Text()
    headers_json = fields.Text()
    job_uuid = fields.Char(index=True)
