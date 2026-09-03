import json
import uuid

from odoo import fields, models

from ..models.casino_api_operation import CasinoApiBusinessError

from decimal import Decimal, ROUND_DOWN


class CasinoApiGatewayService(models.AbstractModel):
    _name = "casino.api.gateway.service"
    _description = "Casino API Gateway Service"

    def handle_http_request(self, operation_code, payload, headers, response_format="legacy"):
        normalized = self._normalize_payload(operation_code, payload)
        provider = self._get_provider(normalized["meta"]["provider_code"])
        self._validate(normalized, provider)

        operation, action = self._register_or_reuse(payload, normalized, provider)
        header_dict = dict(headers.items()) if hasattr(headers, "items") else {}

        if action == "new":
            operation.add_audit_event("accepted", payload=normalized, headers=header_dict, http_status=202)
            operation._process_single()
            body = self._build_response(operation, response_format=response_format)
            return body, 200 if operation.state == "applied" else 422 if operation.state == "rejected" else 500

        if action == "in_progress":
            body = self._build_response(operation, response_format=response_format)
            body["status"] = "accepted"
            body["errors"] = [{"code": "operation_in_progress", "message": "La operacion ya se esta procesando."}]
            return body, 202

        body = self._build_response(operation, response_format=response_format)
        return body, 200 if operation.state == "applied" else 409 if operation.error_code == "duplicate_operation_conflict" else 422 if operation.state == "rejected" else 500 if operation.state == "failed" else 200

    def get_status_payload(self, request_id, response_format="legacy"):
        operation = self.env["casino.api.operation"].sudo().search([("request_id", "=", request_id)], limit=1)
        if not operation:
            if response_format == "middleware":
                return {
                    "status": "error",
                    "provider_code": "",
                    "operation": "wallet.get_operation_status",
                    "payload": {},
                    "errors": [{"code": "operation_not_found", "message": "Operacion no encontrada."}],
                }, 404
            return {
                "meta": {"request_id": request_id},
                "status": "error",
                "result": {},
                "errors": [{"code": "operation_not_found", "message": "Operacion no encontrada."}],
            }, 404
        return self._build_response(operation, response_format=response_format), 200

    def get_status_from_payload(self, payload, response_format="middleware"):
        provider_code = payload.get("provider_code")
        operation_id = payload.get("operation_id") or (payload.get("payload") or {}).get("operation_id")
        if not provider_code:
            raise CasinoApiBusinessError("invalid_payload", "provider_code es obligatorio.", 400)
        if not operation_id:
            raise CasinoApiBusinessError("invalid_payload", "operation_id es obligatorio.", 400)

        operation = self.env["casino.api.operation"].sudo().search(
            [("provider_code", "=", provider_code), ("operation_key", "=", str(operation_id))],
            limit=1,
        )
        if not operation:
            operation = self.env["casino.api.operation"].sudo().search(
                [("provider_code", "=", provider_code), ("request_id", "=", str(operation_id))],
                limit=1,
            )
        if not operation:
            return {
                "status": "error",
                "provider_code": provider_code,
                "operation": "wallet.get_operation_status",
                "payload": {},
                "errors": [{"code": "operation_not_found", "message": "Operacion no encontrada."}],
            }, 404
        return self._build_response(operation, response_format=response_format), 200

    def execute_operation(self, operation):
        normalized = operation.normalized_payload()
        operation_code = normalized["meta"]["operation"]
        if operation_code == "session.authorize":
            return self._execute_authorize(operation, normalized)
        if operation_code == "wallet.get_balance":
            return self._execute_balance(operation, normalized)
        if operation_code == "wallet.apply_operation":
            return self._execute_wallet_operation(operation, normalized)
        raise CasinoApiBusinessError("invalid_operation", "Operacion no soportada.", 400)

    def _normalize_payload(self, operation_code, payload):
        if payload.get("meta") is not None or payload.get("data") is not None:
            meta = dict(payload.get("meta") or {})
            data = dict(payload.get("data") or {})
        else:
            meta = {
                "api_version": payload.get("api_version", "v1"),
                "provider_code": payload.get("provider_code"),
                "operation": payload.get("operation") or operation_code,
                "trace_id": payload.get("trace_id"),
                "request_id": payload.get("request_id"),
            }
            data = dict(payload.get("payload") or {})
            if payload.get("operation_id") and not data.get("operation_id"):
                data["operation_id"] = payload.get("operation_id")

        if not meta.get("api_version"):
            meta["api_version"] = "v1"
        if not meta.get("operation"):
            meta["operation"] = operation_code
        if not meta.get("trace_id"):
            meta["trace_id"] = uuid.uuid4().hex
        if not meta.get("request_id"):
            meta["request_id"] = uuid.uuid4().hex
        return {
            "meta": meta,
            "data": data,
        }

    def _build_response(self, operation, response_format="legacy"):
        if response_format == "middleware":
            return operation.build_middleware_response()
        return operation.build_status_response()

    def _fingerprint_payload(self, operation_model, normalized):
        payload_for_fingerprint = {
            "meta": {
                "api_version": normalized["meta"].get("api_version"),
                "provider_code": normalized["meta"].get("provider_code"),
                "operation": normalized["meta"].get("operation"),
            },
            "data": normalized["data"],
        }
        return operation_model._fingerprint(payload_for_fingerprint)

    def _get_provider(self, provider_code):
        if not provider_code:
            raise CasinoApiBusinessError("invalid_payload", "provider_code es obligatorio.", 400)
        provider = self.env["casino.api.provider"].sudo().search(
            [("code", "=", provider_code), ("active", "=", True)],
            limit=1,
        )
        if not provider:
            raise CasinoApiBusinessError("provider_not_supported", "Proveedor no soportado.", 422)
        return provider

    def _validate(self, normalized, provider):
        meta = normalized["meta"]
        data = normalized["data"]
        required_meta = ["api_version", "provider_code", "operation", "trace_id", "request_id"]
        for field_name in required_meta:
            if not meta.get(field_name):
                raise CasinoApiBusinessError("invalid_payload", f"meta.{field_name} es obligatorio.", 400)

        operation_code = meta["operation"]
        if operation_code == "session.authorize":
            if not data.get("session_token"):
                raise CasinoApiBusinessError("invalid_payload", "data.session_token es obligatorio.", 400)
        elif operation_code == "wallet.get_balance":
            if not data.get("session_token"):
                raise CasinoApiBusinessError("invalid_payload", "data.session_token es obligatorio.", 400)
        elif operation_code == "wallet.apply_operation":
            for field_name in ("session_token", "operation_id", "operation_type", "amount"):
                if data.get(field_name) in (None, "", False):
                    raise CasinoApiBusinessError("invalid_payload", f"data.{field_name} es obligatorio.", 400)
            if data["operation_type"] not in {"stake", "payout"}:
                raise CasinoApiBusinessError("invalid_payload", "data.operation_type no soportado.", 400)
            amount = float(data["amount"])
            if amount <= 0:
                raise CasinoApiBusinessError("invalid_payload", "data.amount debe ser mayor a 0.", 400)
            if data["operation_type"] == "stake" and provider.require_round_id_for_stake and not data.get("round_id"):
                raise CasinoApiBusinessError("invalid_payload", "data.round_id es obligatorio para stake.", 400)
            if data["operation_type"] == "payout" and provider.require_round_id_for_payout and not data.get("round_id"):
                raise CasinoApiBusinessError("invalid_payload", "data.round_id es obligatorio para payout.", 400)
        else:
            raise CasinoApiBusinessError("invalid_operation", "Operacion no soportada.", 400)

    def _provider_request_payload(self, raw_payload):
        provider_request_payload = raw_payload.get("provider_request_payload") if isinstance(raw_payload, dict) else {}
        return dict(provider_request_payload or {})

    def _extract_tracking_values(self, raw_payload, normalized):
        provider_request_payload = self._provider_request_payload(raw_payload)
        data = normalized["data"]
        operation_context = data.get("operation_context") or {}
        return {
            "provider_request_payload_json": self.env["casino.api.operation"]._json_dumps(provider_request_payload),
            "provider_game_id": provider_request_payload.get("gameId") or data.get("provider_game_id") or data.get("game_id"),
            "round_id": data.get("round_id") or provider_request_payload.get("roundId"),
            "event_id": operation_context.get("event_id") or provider_request_payload.get("event_id"),
            "market_id": operation_context.get("market_id") or provider_request_payload.get("market_id"),
            "start": operation_context.get("start_at") or provider_request_payload.get("start"),
        }

    def _register_or_reuse(self, raw_payload, normalized, provider):
        operation_model = self.env["casino.api.operation"].sudo()
        idempotency_key, operation_key, business_key = self._build_keys(normalized)
        fingerprint = self._fingerprint_payload(operation_model, normalized)
        existing = operation_model.search([("idempotency_key", "=", idempotency_key)], limit=1)
        if existing:
            if existing.payload_fingerprint != fingerprint:
                existing.write(
                    {
                        "state": "rejected",
                        "error_code": "duplicate_operation_conflict",
                        "error_message": "La clave de idempotencia ya existe con otro payload.",
                    }
                )
                return existing, "replay"
            if existing.state in {"accepted", "queued", "processing"}:
                return existing, "in_progress"
            return existing, "replay"

        tracking_values = self._extract_tracking_values(raw_payload, normalized)
        operation = operation_model.create(
            {
                "request_id": normalized["meta"]["request_id"],
                "trace_id": normalized["meta"]["trace_id"],
                "provider_code": normalized["meta"]["provider_code"],
                "operation_code": normalized["meta"]["operation"],
                "operation_key": operation_key,
                "idempotency_key": idempotency_key,
                "business_key": business_key,
                "request_payload_json": operation_model._json_dumps(raw_payload),
                "normalized_payload_json": operation_model._json_dumps(normalized),
                "payload_fingerprint": fingerprint,
                "provider_id": provider.id,
                "state": "accepted",
                **tracking_values,
            }
        )
        return operation, "new"

    def _build_keys(self, normalized):
        meta = normalized["meta"]
        data = normalized["data"]
        provider_code = meta["provider_code"]
        operation_code = meta["operation"]
        request_id = str(meta["request_id"])

        if operation_code == "wallet.apply_operation":
            operation_key = str(data["operation_id"])
            business_key = "|".join(
                [
                    provider_code,
                    operation_code,
                    str(data.get("session_token") or ""),
                    str(data.get("round_id") or ""),
                    str(data.get("operation_type") or ""),
                    str(data.get("amount") or ""),
                ]
            )
            idempotency_key = "|".join([provider_code, operation_code, operation_key])
        elif operation_code in {"session.authorize", "wallet.get_balance"}:
            operation_key = request_id
            business_key = "|".join([provider_code, operation_code, str(data.get("session_token") or "")])
            idempotency_key = "|".join([provider_code, operation_code, request_id])
        else:
            operation_key = request_id
            business_key = "|".join([provider_code, operation_code, operation_key])
            idempotency_key = "|".join([provider_code, operation_code, operation_key])

        return idempotency_key, operation_key, business_key

    def _find_partner_by_token(self, token):
        partner = self.env["res.partner"].sudo().search(
            ["|", ("secret_token", "=", token), ("token", "=", token)],
            limit=1,
        )
        if not partner:
            raise CasinoApiBusinessError("invalid_token", "Token invalido.", 422)
        return partner

    def _find_user_for_partner(self, partner):
        user = self.env["res.users"].sudo().search([("partner_id", "=", partner.id)], limit=1)
        if not user:
            raise CasinoApiBusinessError("invalid_token", "No existe un usuario asociado al token.", 422)
        return user

    def _serialize_currency(self):
        return self.env.company.currency_id.name or self.env.company.currency_id.display_name

    def _session_provider_payload_json(self, operation, normalized):
        provider_request_payload = operation.provider_request_payload()
        payload = provider_request_payload or normalized
        return operation._json_dumps(payload)

    def _execute_authorize(self, operation, normalized):
        token = normalized["data"]["session_token"]
        partner = self._find_partner_by_token(token)
        user = self._find_user_for_partner(partner)

        if not partner.secret_token:
            partner.write({"secret_token": self.env["res.partner"]._generate_unique_token("secret_token")})

        now_dt = fields.Datetime.now()
        session = self.env["casino.game.session"].sudo().create(
            {
                "token": partner.secret_token,
                "game_id": False,
                "provider_game_id": operation.provider_game_id,
                "end_round": False,
                "round_id": operation.round_id or False,
                "transaction_id": normalized["meta"]["request_id"],
                "amount": 0.0,
                "event_id": operation.event_id or False,
                "market_id": operation.market_id or False,
                "start": operation.start or False,
                "user_id": user.id,
                "start_datetime": now_dt,
                "initial_balance": partner.balance_game,
                "final_balance": partner.balance_game,
                "currency_id": self.env.company.currency_id.id,
                "result": "started",
                "state": "logged_in",
                "description": "Session authorize via casino_api_gateway",
                "json_data": self._session_provider_payload_json(operation, normalized),
                "provider_request_payload_json": operation.provider_request_payload_json,
                "internal_transaction_id": normalized["meta"]["request_id"],
            }
        )

        return {
            "operation_state": "applied",
            "session_token": partner.secret_token,
            "remote_player_id": str(partner.id),
            "balance": partner.balance_game,
            "currency": self._serialize_currency(),
            "session_id": str(session.id),
            "nickname": partner.nickname or partner.name,
            "provider_balance": int(round(float(partner.balance_game) * 100)),
            "provider_currency_code": 0,
            "timestamp": int(now_dt.timestamp() * 1000),
            "country": (
                partner.country_id.code
                or partner.commercial_partner_id.country_id.code
                or "AR"
            ),
        }

    def _execute_balance(self, operation, normalized):
        token = normalized["data"]["session_token"]
        partner = self._find_partner_by_token(token)
        return {
            "operation_state": "applied",
            "balance": partner.balance_game,
            "currency": self._serialize_currency(),
            "provider_balance": int(round(float(partner.balance_game) * 100)),
            "provider_currency_code": 0,
            "timestamp": int(fields.Datetime.now().timestamp() * 1000),
        }

    def _execute_wallet_operation(self, operation, normalized):
        data = normalized["data"]
        token = data["session_token"]
        partner = self._find_partner_by_token(token)
        user = self._find_user_for_partner(partner)

        amount = float(data["amount"]) / 100
        operation_type = data["operation_type"]
        previous_balance = partner.balance_game
        if operation_type == "stake":
            if amount > previous_balance:
                raise CasinoApiBusinessError("insufficient_funds", "Saldo insuficiente.", 422)
            result = "in_progress" if not data.get("round_finished") else "loss"
            state = "in_progress" if not data.get("round_finished") else "finished"
        else:
            result = "win"
            state = "finished"

        # Delegate to centralized money.flow — single writer of balance_game
        flow_op = 'bet' if operation_type == 'stake' else 'win'
        tx = self.env['casino.money.flow'].new().process_operation(
            operation_type=flow_op,
            partner_id=partner,
            amount=amount,
            idempotency_key=operation.idempotency_key,
            external_reference=data["operation_id"],
            origin_model='casino.api.operation',
            origin_id=operation.id,
            note='Gateway %s via %s' % (operation_type, normalized["meta"]["provider_code"]),
        )
        new_balance = tx.balance_after

        provider_request_payload = operation.provider_request_payload()
        provider_game_id = operation.provider_game_id or provider_request_payload.get("gameId")
        game = False
        if provider_game_id:
            game = self.env["product.product"].sudo().search([("game_id", "=", provider_game_id)], limit=1)

        operation_context = data.get("operation_context") or {}
        now_dt = fields.Datetime.now()
        session = self.env["casino.game.session"].sudo().create(
            {
                "token": partner.secret_token or token,
                "game_id": game.id if game else False,
                "provider_game_id": provider_game_id,
                "end_round": bool(data.get("round_finished")),
                "round_id": operation.round_id or data.get("round_id") or provider_request_payload.get("roundId"),
                "transaction_id": data["operation_id"],
                "amount": amount,
                "event_id": operation.event_id or operation_context.get("event_id") or provider_request_payload.get("event_id"),
                "event_date": operation_context.get("event_date"),
                "market_id": operation.market_id or operation_context.get("market_id") or provider_request_payload.get("market_id"),
                "start": operation.start or operation_context.get("start_at") or provider_request_payload.get("start"),
                "token_live": bool(operation_context.get("token_live")),
                "user_id": user.id,
                "start_datetime": now_dt,
                "initial_balance": previous_balance,
                "final_balance": new_balance,
                "to_win": 0.0,
                "events": json.dumps(operation_context.get("events") or []),
                "currency_id": self.env.company.currency_id.id,
                "result": result,
                "state": state,
                "description": "wallet.apply_operation via casino_api_gateway",
                "json_data": self._session_provider_payload_json(operation, normalized),
                "provider_request_payload_json": operation.provider_request_payload_json,
                "internal_transaction_id": operation.request_id,
            }
        )

        valor = Decimal(str(new_balance))
        new_balance = int((valor * Decimal("100")).to_integral_value(rounding=ROUND_DOWN))

        return {
            "operation_state": "applied",
            "operation_id": data["operation_id"],
            "balance": new_balance,
            "currency": self._serialize_currency(),
            "provider_transaction_id": session.transaction_id,
            "session_id": str(session.id),
            "result": result,
            "state": state,
            "provider_balance": int(round(float(new_balance))),
            "provider_currency_code": 0,
            "response_transaction_id": operation.request_id,
            "timestamp": int(now_dt.timestamp() * 1000),
        }
