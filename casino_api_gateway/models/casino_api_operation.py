import json
import logging
from hashlib import sha256

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CasinoApiBusinessError(Exception):
    def __init__(self, code, message, http_status=422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


class CasinoApiOperation(models.Model):
    _name = "casino.api.operation"
    _description = "Casino API Operation"
    _order = "id desc"

    name = fields.Char(required=True, default=lambda self: self.env["ir.sequence"].next_by_code("casino.api.operation") or "/")
    request_id = fields.Char(required=True, index=True)
    trace_id = fields.Char(required=True, index=True)
    provider_code = fields.Char(required=True, index=True)
    operation_code = fields.Char(required=True, index=True)
    operation_key = fields.Char(index=True)
    idempotency_key = fields.Char(required=True, index=True)
    business_key = fields.Char(index=True)
    state = fields.Selection(
        [
            ("accepted", "Accepted"),
            ("queued", "Queued"),
            ("processing", "Processing"),
            ("applied", "Applied"),
            ("rejected", "Rejected"),
            ("failed", "Failed"),
            ("duplicate", "Duplicate"),
        ],
        default="accepted",
        required=True,
        index=True,
    )
    request_payload_json = fields.Text(required=True)
    provider_request_payload_json = fields.Text()
    normalized_payload_json = fields.Text(required=True)
    response_payload_json = fields.Text()
    error_code = fields.Char(index=True)
    error_message = fields.Char()
    payload_fingerprint = fields.Char(index=True)
    job_uuid = fields.Char(index=True)
    attempt_count = fields.Integer(default=0)
    processed_at = fields.Datetime()
    provider_id = fields.Many2one("casino.api.provider", ondelete="restrict", index=True)
    provider_game_id = fields.Char(string="Game ID Proveedor", index=True)
    round_id = fields.Char(string="Ronda", index=True)
    event_id = fields.Char(string="ID Evento", index=True)
    market_id = fields.Char(string="Mercado", index=True)
    start = fields.Char(string="Inicio de Juego")

    _sql_constraints = [
        ("casino_api_operation_request_id_uniq", "unique(request_id)", "El request_id debe ser unico."),
        ("casino_api_operation_idempotency_uniq", "unique(idempotency_key)", "La clave de idempotencia debe ser unica."),
    ]

    @api.model
    def _json_dumps(self, payload):
        return json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))

    @api.model
    def _fingerprint(self, payload):
        return sha256(self._json_dumps(payload).encode("utf-8")).hexdigest()

    def _payload_dict(self, field_name):
        self.ensure_one()
        raw = self[field_name]
        return json.loads(raw) if raw else {}

    def request_payload(self):
        return self._payload_dict("request_payload_json")

    def provider_request_payload(self):
        return self._payload_dict("provider_request_payload_json")

    def normalized_payload(self):
        return self._payload_dict("normalized_payload_json")

    def response_payload(self):
        return self._payload_dict("response_payload_json")

    def add_audit_event(self, event_type, *, payload=None, headers=None, http_status=None, message=None):
        audit_vals = {
            "operation_id": self.id,
            "trace_id": self.trace_id,
            "event_type": event_type,
            "http_status": http_status,
            "message": message,
            "job_uuid": self.job_uuid,
            "payload_json": self._json_dumps(payload),
            "headers_json": self._json_dumps(headers),
        }
        return self.env["casino.api.audit.event"].sudo().create(audit_vals)

    def build_status_response(self):
        self.ensure_one()
        normalized = self.normalized_payload()
        response_payload = self.response_payload()
        status = "accepted"
        if self.state == "applied":
            status = "success"
        elif self.state in {"rejected", "failed"}:
            status = "error"
        result = {
            "operation_state": self.state,
            "provider_code": self.provider_code,
            "operation": self.operation_code,
        }
        if response_payload:
            result.update(response_payload)
        errors = []
        if self.error_code:
            errors.append(
                {
                    "code": self.error_code,
                    "message": self.error_message or self.error_code,
                }
            )
        return {
            "meta": {
                "api_version": normalized.get("meta", {}).get("api_version", "v1"),
                "trace_id": self.trace_id,
                "request_id": self.request_id,
                "operation": self.operation_code,
            },
            "status": status,
            "result": result,
            "errors": errors,
        }

    def build_middleware_response(self):
        self.ensure_one()
        response_payload = self.response_payload()
        status = "accepted"
        if self.state == "applied":
            status = "success"
        elif self.state in {"rejected", "failed"}:
            status = "error"
        errors = []
        if self.error_code:
            errors.append(
                {
                    "code": self.error_code,
                    "message": self.error_message or self.error_code,
                }
            )
        return {
            "status": status,
            "provider_code": self.provider_code,
            "operation": self.operation_code,
            "payload": response_payload or {},
            "errors": errors,
        }

    def process_async(self):
        for operation in self:
            operation._process_single()

    def _process_single(self):
        self.ensure_one()
        self.write(
            {
                "state": "processing",
                "attempt_count": self.attempt_count + 1,
            }
        )
        self.add_audit_event("processing", payload=self.normalized_payload())

        gateway = self.env["casino.api.gateway.service"].sudo()
        try:
            result = gateway.execute_operation(self)
            self.write(
                {
                    "state": "applied",
                    "response_payload_json": self._json_dumps(result),
                    "processed_at": fields.Datetime.now(),
                    "error_code": False,
                    "error_message": False,
                }
            )
            self.add_audit_event("applied", payload=result, http_status=200)
        except CasinoApiBusinessError as exc:
            _logger.info("Casino API business error for %s: %s", self.request_id, exc.code)
            self.write(
                {
                    "state": "rejected",
                    "error_code": exc.code,
                    "error_message": exc.message,
                    "processed_at": fields.Datetime.now(),
                }
            )
            self.add_audit_event(
                "rejected",
                payload={"code": exc.code, "message": exc.message},
                http_status=exc.http_status,
                message=exc.message,
            )
        except Exception as exc:
            _logger.exception("Casino API unexpected failure for %s", self.request_id)
            self.write(
                {
                    "state": "failed",
                    "error_code": "internal_error",
                    "error_message": str(exc),
                    "processed_at": fields.Datetime.now(),
                }
            )
            self.add_audit_event(
                "failed",
                payload={"code": "internal_error", "message": str(exc)},
                http_status=500,
                message=str(exc),
            )
