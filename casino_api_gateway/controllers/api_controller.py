import json
import logging

from odoo import http
from odoo.http import Response, request

from ..models.casino_api_operation import CasinoApiBusinessError

_logger = logging.getLogger(__name__)


class CasinoApiController(http.Controller):
    def _service(self):
        return request.env["casino.api.gateway.service"].sudo()

    def _json_response(self, payload, status):
        return Response(
            json.dumps(payload),
            status=status,
            content_type="application/json",
        )

    def _middleware_error_response(self, operation_code, payload, exc, status):
        return {
            "status": "error",
            "provider_code": payload.get("provider_code") or ((payload.get("meta") or {}).get("provider_code")) or "",
            "operation": operation_code,
            "payload": {},
            "errors": [{"code": exc.code if hasattr(exc, 'code') else "internal_error", "message": str(exc.message if hasattr(exc, 'message') else exc)}],
        }, status

    def _legacy_error_response(self, operation_code, payload, exc, status):
        return {
            "meta": {
                "api_version": (payload.get("meta") or {}).get("api_version", "v1"),
                "operation": operation_code,
            },
            "status": "error",
            "result": {},
            "errors": [{"code": exc.code if hasattr(exc, 'code') else "internal_error", "message": str(exc.message if hasattr(exc, 'message') else exc)}],
        }, status

    def _handle(self, operation_code, response_format="legacy"):
        payload = request.get_json_data() or {}
        try:
            result, status = self._service().handle_http_request(
                operation_code,
                payload,
                request.httprequest.headers,
                response_format=response_format,
            )
            return self._json_response(result, status)
        except CasinoApiBusinessError as exc:
            body, status_code = (
                self._middleware_error_response(operation_code, payload, exc, exc.http_status)
                if response_format == "middleware"
                else self._legacy_error_response(operation_code, payload, exc, exc.http_status)
            )
            return self._json_response(body, status_code)
        except Exception as exc:
            _logger.exception("Casino API controller unexpected error")
            body, status_code = (
                self._middleware_error_response(operation_code, payload, exc, 500)
                if response_format == "middleware"
                else self._legacy_error_response(operation_code, payload, exc, 500)
            )
            return self._json_response(body, status_code)

    @http.route("/casino_api/v1/sessions/authorize", type="http", auth="public", methods=["POST"], csrf=False)
    def authorize_session(self, **kwargs):
        return self._handle("session.authorize")

    @http.route("/casino_api/v1/wallet/balance", type="http", auth="public", methods=["POST"], csrf=False)
    def wallet_balance(self, **kwargs):
        return self._handle("wallet.get_balance")

    @http.route("/casino_api/v1/wallet/operations", type="http", auth="public", methods=["POST"], csrf=False)
    def wallet_operation(self, **kwargs):
        return self._handle("wallet.apply_operation")

    @http.route("/casino_api/v1/operations/<string:request_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def operation_status(self, request_id, **kwargs):
        result, status = self._service().get_status_payload(request_id)
        return self._json_response(result, status)

    @http.route("/sessions/authorize", type="http", auth="public", methods=["POST"], csrf=False)
    def middleware_authorize_session(self, **kwargs):
        return self._handle("session.authorize", response_format="middleware")

    @http.route("/wallets/balance", type="http", auth="public", methods=["POST"], csrf=False)
    def middleware_wallet_balance(self, **kwargs):
        return self._handle("wallet.get_balance", response_format="middleware")

    @http.route("/wallets/operations", type="http", auth="public", methods=["POST"], csrf=False)
    def middleware_wallet_operation(self, **kwargs):
        return self._handle("wallet.apply_operation", response_format="middleware")

    @http.route("/wallets/operations/status", type="http", auth="public", methods=["POST"], csrf=False)
    def middleware_operation_status(self, **kwargs):
        payload = request.get_json_data() or {}
        try:
            result, status = self._service().get_status_from_payload(payload, response_format="middleware")
            return self._json_response(result, status)
        except CasinoApiBusinessError as exc:
            body, status_code = self._middleware_error_response("wallet.get_operation_status", payload, exc, exc.http_status)
            return self._json_response(body, status_code)
        except Exception as exc:
            _logger.exception("Casino API middleware status unexpected error")
            body, status_code = self._middleware_error_response("wallet.get_operation_status", payload, exc, 500)
            return self._json_response(body, status_code)
