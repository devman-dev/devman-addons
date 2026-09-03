import json
import uuid

from odoo import fields, models

from ..models.casino_api_operation import CasinoApiBusinessError


class CasinoApiGatewayService(models.AbstractModel):
    _name = "casino.api.gateway.service"
    _description = "Casino API Gateway Service"

    def handle_http_request(self, operation_code, payload, headers):
        normalized = self._normalize_payload(operation_code, payload)
        provider = self._get_provider(normalized["meta"]["provider_code"])
        self._validate(normalized, provider)

        operation, action = self._register_or_reuse(payload, normalized, provider)
        header_dict = dict(headers.items()) if hasattr(headers, "items") else {}

        if action == "new":
            operation.add_audit_event("accepted", payload=normalized, headers=header_dict, http_status=202)
            operation._process_single()
            body = operation.build_status_response()
            return body, 200 if operation.state == "applied" else 422 if operation.state == "rejected" else 500

        if action == "in_progress":
            body = operation.build_status_response()
            body["status"] = "accepted"
            body["errors"] = [{"code": "operation_in_progress", "message": "La operacion ya se esta procesando."}]
            return body, 202

        body = operation.build_status_response()
        return body, 200 if operation.state == "applied" else 409 if operation.error_code == "duplicate_operation_conflict" else 422 if operation.state == "rejected" else 500 if operation.state == "failed" else 200

    def get_status_payload(self, request_id):
        operation = self.env["casino.api.operation"].sudo().search([("request_id", "=", request_id)], limit=1)
        if not operation:
            return {
                "meta": {"request_id": request_id},
                "status": "error",
                "result": {},
                "errors": [{"code": "operation_not_found", "message": "Operacion no encontrada."}],
            }, 404
        return operation.build_status_response(), 200

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
        meta = dict(payload.get("meta") or {})
        data = dict(payload.get("data") or {})
        meta.setdefault("api_version", "v1")
        meta.setdefault("operation", operation_code)
        meta.setdefault("trace_id", uuid.uuid4().hex)
        meta.setdefault("request_id", uuid.uuid4().hex)
        return {
            "meta": meta,
            "data": data,
        }

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

    def _register_or_reuse(self, raw_payload, normalized, provider):
        operation_model = self.env["casino.api.operation"].sudo()
        idempotency_key, operation_key, business_key = self._build_keys(normalized)
        fingerprint = operation_model._fingerprint(normalized)
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
            }
        )
        return operation, "new"

    def _build_keys(self, normalized):
        meta = normalized["meta"]
        data = normalized["data"]
        provider_code = meta["provider_code"]
        operation_code = meta["operation"]

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
        elif operation_code in {"session.authorize", "wallet.get_balance"}:
            operation_key = str(data.get("session_token"))
            business_key = "|".join([provider_code, operation_code, operation_key])
        else:
            operation_key = meta["request_id"]
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

    def _execute_authorize(self, operation, normalized):
        token = normalized["data"]["session_token"]
        partner = self._find_partner_by_token(token)
        user = self._find_user_for_partner(partner)

        if not partner.secret_token:
            partner.write({"secret_token": self.env["res.partner"]._generate_unique_token("secret_token")})

        session = self.env["casino.game.session"].sudo().create(
            {
                "token": partner.secret_token,
                "game_id": False,
                "end_round": False,
                "round_id": False,
                "transaction_id": normalized["meta"]["request_id"],
                "amount": 0.0,
                "user_id": user.id,
                "start_datetime": fields.Datetime.now(),
                "initial_balance": partner.balance_game,
                "final_balance": partner.balance_game,
                "currency_id": self.env.company.currency_id.id,
                "result": "started",
                "state": "logged_in",
                "description": "Session authorize via casino_api_gateway",
                "json_data": json.dumps(normalized, sort_keys=True),
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
        }

    def _execute_balance(self, operation, normalized):
        token = normalized["data"]["session_token"]
        partner = self._find_partner_by_token(token)
        return {
            "operation_state": "applied",
            "balance": partner.balance_game,
            "currency": self._serialize_currency(),
        }

    def _execute_wallet_operation(self, operation, normalized):
        data = normalized["data"]
        token = data["session_token"]
        partner = self._find_partner_by_token(token)
        user = self._find_user_for_partner(partner)

        amount = float(data["amount"])
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

        flow_op = 'bet' if operation_type == 'stake' else 'win'
        tx = self.env['casino.money.flow'].new().process_operation(
            operation_type=flow_op,
            partner_id=partner,
            amount=amount,
            idempotency_key=operation.idempotency_key,
            external_reference=data["operation_id"],
            origin_model='casino.api.operation',
            origin_id=operation.id,
            note='Gateway RESPA %s via %s' % (operation_type, normalized["meta"]["provider_code"]),
        )
        new_balance = tx.balance_after

        game = False
        provider_game_id = data.get("provider_game_id") or data.get("game_id")
        if provider_game_id:
            game = self.env["product.product"].sudo().search([("game_id", "=", provider_game_id)], limit=1)

        operation_context = data.get("operation_context") or {}
        session = self.env["casino.game.session"].sudo().create(
            {
                "token": partner.secret_token or token,
                "game_id": game.id if game else False,
                "end_round": bool(data.get("round_finished")),
                "round_id": data.get("round_id"),
                "transaction_id": data["operation_id"],
                "amount": amount,
                "event_id": operation_context.get("event_id"),
                "event_date": operation_context.get("event_date"),
                "market_id": operation_context.get("market_id"),
                "start": operation_context.get("start_at"),
                "token_live": bool(operation_context.get("token_live")),
                "user_id": user.id,
                "start_datetime": fields.Datetime.now(),
                "initial_balance": previous_balance,
                "final_balance": new_balance,
                "to_win": 0.0,
                "events": json.dumps(operation_context.get("events") or []),
                "currency_id": self.env.company.currency_id.id,
                "result": result,
                "state": state,
                "description": "wallet.apply_operation via casino_api_gateway",
                "json_data": json.dumps(normalized, sort_keys=True),
                "internal_transaction_id": operation.request_id,
            }
        )

        return {
            "operation_state": "applied",
            "balance": new_balance,
            "currency": self._serialize_currency(),
            "provider_transaction_id": session.transaction_id,
            "session_id": str(session.id),
            "result": result,
            "state": state,
        }
