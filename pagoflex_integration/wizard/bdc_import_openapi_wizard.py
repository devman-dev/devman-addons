from odoo import fields, models, _
from odoo.exceptions import UserError

import requests

class BdcImportOpenApiWizard(models.TransientModel):
    _name = "bdc.import.openapi.wizard"
    _description = "BDC Import OpenAPI Wizard"

    openapi_json_url = fields.Char(
        string="OpenAPI JSON URL",
        required=True,
        help="Paste the OpenAPI JSON URL (usually shown in Swagger UI as /openapi.json or Download JSON).",
    )
    prefix_code = fields.Char(
        string="Endpoint Code Prefix",
        default="BDC_",
        help="Prefix used to create endpoint codes. Codes are generated as PREFIX + METHOD + _ + sanitized PATH.",
    )
    timeout = fields.Integer(default=30)

    imported_count = fields.Integer(readonly=True)

    def action_import(self):
        self.ensure_one()
        url = (self.openapi_json_url or "").strip()
        if not url:
            raise UserError(_("OpenAPI JSON URL is required."))

        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            spec = resp.json()
        except Exception as e:
            raise UserError(_("Could not fetch/parse OpenAPI JSON: %s") % (str(e),))

        paths = spec.get("paths") or {}
        if not paths:
            raise UserError(_("OpenAPI document has no 'paths' section."))

        def sanitize(s):
            s = s.strip().strip("/")
            s = s.replace("/", "_").replace("{", "").replace("}", "")
            s = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in s)
            while "__" in s:
                s = s.replace("__", "_")
            return s.upper() or "ROOT"

        Endpoint = self.env["bdc.endpoint"]
        company = self.env.company
        created = 0

        for path, ops in paths.items():
            if not isinstance(ops, dict):
                continue
            for method, op in ops.items():
                method_u = str(method).upper()
                if method_u not in ("GET","POST","PUT","PATCH","DELETE"):
                    continue
                op = op or {}
                name = op.get("summary") or op.get("operationId") or f"{method_u} {path}"
                desc = op.get("description") or ""
                code = f"{self.prefix_code}{method_u}_{sanitize(path)}"
                vals = {
                    "company_id": company.id,
                    "code": code,
                    "name": name,
                    "method": method_u,
                    "path": path,
                    "description": desc,
                    "requires_auth": True,
                    "openapi_source": url,
                }
                existing = Endpoint.search([("company_id","=",company.id),("code","=",code)], limit=1)
                if existing:
                    existing.write(vals)
                else:
                    Endpoint.create(vals)
                    created += 1

        self.imported_count = created

        return {
            "type": "ir.actions.act_window",
            "res_model": "bdc.import.openapi.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
