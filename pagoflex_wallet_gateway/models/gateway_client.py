import json
import logging
from datetime import datetime, timezone

import requests
from odoo import _, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayClientMixin(models.AbstractModel):
    _name = "pf.gateway.client.mixin"
    _description = "Cliente API de PagoFlex Gateway"

    def _gateway_param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    def _gateway_base_url(self):
        base_url = (self._gateway_param("pagoflex_wallet_gateway.base_url", "") or "").strip()
        if not base_url:
            raise UserError(_("Configura la URL base del gateway en Ajustes antes de sincronizar."))
        return base_url.rstrip("/")

    def _gateway_api_key(self):
        api_key = (self._gateway_param("pagoflex_wallet_gateway.api_key", "") or "").strip()
        if not api_key:
            raise UserError(_("Configura la API key administrativa del gateway en Ajustes antes de sincronizar."))
        return api_key

    def _gateway_timeout(self):
        raw_value = self._gateway_param("pagoflex_wallet_gateway.timeout_seconds", "60")
        try:
            return max(5, int(raw_value))
        except (TypeError, ValueError):
            return 20

    def _gateway_page_size(self):
        raw_value = self._gateway_param("pagoflex_wallet_gateway.page_size", "200")
        try:
            return min(1000, max(1, int(raw_value)))
        except (TypeError, ValueError):
            return 200

    def _gateway_verify_ssl(self):
        raw_value = (self._gateway_param("pagoflex_wallet_gateway.verify_ssl", "True") or "").strip().lower()
        return raw_value not in {"0", "false", "no"}

    def _gateway_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-Key": self._gateway_api_key(),
        }

    def _gateway_request_json(self, method, path, *, params=None, payload=None):
        url = f"{self._gateway_base_url()}{path}"
        timeout = self._gateway_timeout()
        verify_ssl = self._gateway_verify_ssl()
        headers = self._gateway_headers()
        last_error = None

        for attempt in range(1, 4):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=payload,
                    timeout=timeout,
                    verify=verify_ssl,
                )
                if response.status_code >= 400:
                    detail = response.text[:500] if response.text else response.reason
                    _logger.warning(
                        "Gateway HTTP error method=%s url=%s status=%s detail=%s",
                        method,
                        url,
                        response.status_code,
                        detail,
                    )
                    if response.status_code < 500:
                        raise UserError(_("El gateway rechazo la solicitud (%s): %s") % (response.status_code, detail))
                    raise UserError(_("El gateway respondio con error (%s): %s") % (response.status_code, detail))
                if not response.text:
                    return {}
                try:
                    return response.json()
                except ValueError as exc:
                    _logger.warning("Gateway returned invalid JSON method=%s url=%s error=%s", method, url, exc)
                    raise UserError(_("El gateway devolvio una respuesta JSON invalida.")) from exc
            except UserError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                _logger.warning(
                    "Gateway request failed method=%s url=%s attempt=%s error=%s",
                    method,
                    url,
                    attempt,
                    exc,
                )

        raise UserError(_("No se pudo consultar el gateway: %s") % last_error)

    def _gateway_paginated_get(self, path, *, updated_since=None, extra_params=None):
        offset = 0
        limit = self._gateway_page_size()
        items = []

        while True:
            params = {"limit": limit, "offset": offset}
            if extra_params:
                params.update({key: value for key, value in extra_params.items() if value not in (None, "")})
            if updated_since:
                if isinstance(updated_since, datetime):
                    if updated_since.tzinfo is None:
                        updated_since = updated_since.replace(tzinfo=timezone.utc)
                    params["updated_since"] = updated_since.isoformat()
                else:
                    params["updated_since"] = str(updated_since)

            payload = self._gateway_request_json("GET", path, params=params)
            batch = payload.get("items") or []
            if not isinstance(batch, list):
                raise UserError(_("La respuesta del gateway para %s no contiene una lista válida.") % path)

            items.extend(batch)
            total = payload.get("total")
            if len(batch) < limit:
                break
            if total is not None and len(items) >= total:
                break
            offset += limit

        return items

    def _payload_to_text(self, payload):
        try:
            return json.dumps(payload or {}, ensure_ascii=False, indent=2, sort_keys=True)
        except TypeError:
            return json.dumps({"raw": str(payload)}, ensure_ascii=False, indent=2, sort_keys=True)

    def _coerce_datetime(self, value, *, field_name="datetime"):
        if not value:
            return False
        if isinstance(value, datetime):
            parsed = value
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed

        text_value = str(value).strip()
        if not text_value:
            return False

        if text_value.endswith("Z"):
            text_value = f"{text_value[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(text_value)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            pass

        # Fallback for common non-ISO formats.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text_value, fmt)
            except ValueError:
                continue

        _logger.warning("Unable to parse %s value from gateway: %s", field_name, value)
        return False

    def _coerce_date(self, value, *, field_name="date"):
        if not value:
            return False

        text_value = str(value).strip()
        if not text_value:
            return False

        try:
            if text_value.endswith("Z"):
                text_value = f"{text_value[:-1]}+00:00"
            return datetime.fromisoformat(text_value).date()
        except ValueError:
            pass

        # Accept plain date strings like YYYY-MM-DD.
        try:
            return datetime.strptime(text_value[:10], "%Y-%m-%d").date()
        except ValueError:
            pass

        # Accept plain date strings like YYYYMMDD (Coelsa / BIND format)
        try:
            return datetime.strptime(text_value[:8], "%Y%m%d").date()
        except ValueError:
            pass
            
        # Accept plain date strings like DD/MM/YYYY
        try:
            return datetime.strptime(text_value[:10], "%d/%m/%Y").date()
        except ValueError:
            _logger.warning("Unable to parse %s value from gateway: %s", field_name, value)
            return False
