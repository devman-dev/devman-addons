from odoo import models, _
from odoo.exceptions import UserError

import json
import time
import logging
import requests

_logger = logging.getLogger(__name__)

class BdcApiService(models.AbstractModel):
    _name = "bdc.api.service"
    _description = "BDC API Service"

    def _company(self):
        return self.env.company

    def _build_url(self, path):
        company = self._company()
        base = (company.bdc_base_url or "").rstrip("/")
        if not base:
            raise UserError(_("BDC Base URL is not configured."))
        path = (path or "").strip()
        if not path.startswith("/"):
            path = "/" + path
        return base + path

    def _headers(self, requires_auth=True, extra=None):
        company = self._company()
        headers = {"Accept": "application/json"}
        if requires_auth and company.bdc_auth_type == "bearer":
            token = company.bdc_get_access_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        if extra:
            headers.update(extra)
        return headers

    def call(self, endpoint, params=None, json_body=None, data=None, headers=None, timeout=30):
        company = self._company()
        ep = endpoint
        method = getattr(ep, "method", None) or ep.get("method")
        path = getattr(ep, "path", None) or ep.get("path")
        requires_auth = getattr(ep, "requires_auth", None)
        if requires_auth is None:
            requires_auth = ep.get("requires_auth", True)

        url = self._build_url(path)
        req_headers = self._headers(requires_auth=requires_auth, extra=headers)

        start = time.time()
        try:
            resp = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                data=data,
                headers=req_headers,
                timeout=timeout,
            )
            duration_ms = int((time.time() - start) * 1000)
            self.env["bdc.request.log"].sudo().create({
                "company_id": company.id,
                "endpoint_id": getattr(ep, "id", False) or False,
                "endpoint_code": getattr(ep, "code", "") or ep.get("code", ""),
                "method": method,
                "url": url,
                "status_code": resp.status_code,
                "duration_ms": duration_ms,
                "request_headers": json.dumps(req_headers, ensure_ascii=False, indent=2),
                "request_params": json.dumps(params or {}, ensure_ascii=False, indent=2),
                "request_body": json.dumps(json_body, ensure_ascii=False, indent=2) if json_body is not None else (data or ""),
                "response_headers": json.dumps(dict(resp.headers), ensure_ascii=False, indent=2),
                "response_body": resp.text,
            })
            return resp
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            self.env["bdc.request.log"].sudo().create({
                "company_id": company.id,
                "endpoint_id": getattr(ep, "id", False) or False,
                "endpoint_code": getattr(ep, "code", "") or ep.get("code", ""),
                "method": method,
                "url": url,
                "duration_ms": duration_ms,
                "request_headers": json.dumps(req_headers, ensure_ascii=False, indent=2),
                "request_params": json.dumps(params or {}, ensure_ascii=False, indent=2),
                "request_body": json.dumps(json_body, ensure_ascii=False, indent=2) if json_body is not None else (data or ""),
                "error": str(e),
            })
            raise

    def cron_refresh_token(self):
        """Placeholder for token refresh.

Implement this method according to BDC's Swagger/OpenAPI definition once you know:
- token endpoint URL
- payload fields
- response fields
"""
        _logger.info("BDC cron_refresh_token: not implemented (placeholder).")
        return True
