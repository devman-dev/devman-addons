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

    def _handle(self, operation_code):
        payload = request.get_json_data() or {}
        try:
            result, status = self._service().handle_http_request(operation_code, payload, request.httprequest.headers)
            return self._json_response(result, status)
        except CasinoApiBusinessError as exc:
            return self._json_response(
                {
                    "meta": {
                        "api_version": (payload.get("meta") or {}).get("api_version", "v1"),
                        "operation": operation_code,
                    },
                    "status": "error",
                    "result": {},
                    "errors": [{"code": exc.code, "message": exc.message}],
                },
                exc.http_status,
            )
        except Exception as exc:
            _logger.exception("Casino API controller unexpected error")
            return self._json_response(
                {
                    "meta": {
                        "api_version": (payload.get("meta") or {}).get("api_version", "v1"),
                        "operation": operation_code,
                    },
                    "status": "error",
                    "result": {},
                    "errors": [{"code": "internal_error", "message": str(exc)}],
                },
                500,
            )

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
