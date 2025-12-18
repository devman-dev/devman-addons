from odoo import fields, models, _
from odoo.exceptions import UserError

import json

class BdcTestCallWizard(models.TransientModel):
    _name = "bdc.test.call.wizard"
    _description = "BDC Test Call Wizard"

    endpoint_id = fields.Many2one("bdc.endpoint", required=True, domain=lambda self: [("company_id", "=", self.env.company.id)])
    params_json = fields.Text(string="Query Params (JSON)", default="{}")
    body_json = fields.Text(string="Body (JSON)", default="{}")
    timeout = fields.Integer(default=30)

    response_status = fields.Integer(readonly=True)
    response_headers = fields.Text(readonly=True)
    response_body = fields.Text(readonly=True)

    def action_execute(self):
        self.ensure_one()
        try:
            params = json.loads(self.params_json or "{}")
        except Exception:
            raise UserError(_("Invalid JSON in Query Params."))
        try:
            body = json.loads(self.body_json or "{}") if (self.body_json or "").strip() else None
        except Exception:
            raise UserError(_("Invalid JSON in Body."))

        service = self.env["bdc.api.service"]
        resp = service.call(self.endpoint_id, params=params, json_body=body, timeout=self.timeout)

        self.write({
            "response_status": resp.status_code,
            "response_headers": json.dumps(dict(resp.headers), ensure_ascii=False, indent=2),
            "response_body": resp.text,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "bdc.test.call.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
