import json
import logging

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayTransfer(models.Model):
    _name = "pf.gateway.transfer"
    _description = "Transferencia de PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "transaction_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(required=True, index=True)
    payment_id = fields.Char(index=True)
    origin_id = fields.Char(index=True)
    status = fields.Char(index=True)
    movement_nature = fields.Selection(
        [
            ("TRANSFER", "Transferencia"),
            ("COMMISSION", "Comisión"),
        ],
        index=True,
    )
    amount = fields.Float(digits=(16, 2))
    currency = fields.Char()
    concept = fields.Char()
    description = fields.Text()
    connector_id = fields.Char(index=True, string="ID Coelsa")
    source_bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta origen", ondelete="set null", index=True)
    destination_bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta destino", ondelete="set null", index=True)
    source_user_id = fields.Many2one("pf.gateway.user", string="Usuario origen", ondelete="set null", index=True)
    destination_user_id = fields.Many2one("pf.gateway.user", string="Usuario destino", ondelete="set null", index=True)
    source_address = fields.Char()
    source_address_type = fields.Char()
    source_owner_id_type = fields.Char()
    source_owner_id = fields.Char()
    source_owner_name = fields.Char()
    destination_address = fields.Char()
    destination_address_type = fields.Char()
    destination_owner_id_type = fields.Char()
    destination_owner_id = fields.Char()
    destination_owner_name = fields.Char()
    extra_metadata = fields.Text()
    connector_response = fields.Text()
    source_address_display = fields.Html(
        string="Origen",
        compute="_compute_address_displays",
        sanitize=False,
    )
    destination_address_display = fields.Html(
        string="Destino",
        compute="_compute_address_displays",
        sanitize=False,
    )
    is_external_incoming_transfer = fields.Boolean(
        string="Entrante externa",
        compute="_compute_dashboard_filter_flags",
        search="_search_is_external_incoming_transfer",
    )
    is_external_outgoing_transfer = fields.Boolean(
        string="Saliente externa",
        compute="_compute_dashboard_filter_flags",
        search="_search_is_external_outgoing_transfer",
    )
    is_dashboard_commission_account_transfer = fields.Boolean(
        string="Cuenta de comisión",
        compute="_compute_dashboard_filter_flags",
        search="_search_is_dashboard_commission_account_transfer",
    )
    is_pagoflex_wallet_transfer = fields.Boolean(
        string="PagoFlex",
        compute="_compute_dashboard_filter_flags",
        search="_search_is_pagoflex_wallet_transfer",
    )
    is_sivep_wallet_transfer = fields.Boolean(
        string="SIVEP",
        compute="_compute_dashboard_filter_flags",
        search="_search_is_sivep_wallet_transfer",
    )
    source_created_at = fields.Datetime()
    source_updated_at = fields.Datetime(index=True)
    transaction_at = fields.Datetime(index=True)
    fecha_negocio = fields.Date(string="Fecha negocio", index=True)
    business_data_last_check_at = fields.Datetime(string="Ultima consulta datos bancarios", index=True)
    status_validation_attempts = fields.Integer(
        string="Intentos validacion estado",
        default=0,
        index=True,
        readonly=True,
    )
    status_validation_last_at = fields.Datetime(
        string="Ultima validacion estado",
        index=True,
        readonly=True,
    )
    status_validation_exhausted = fields.Boolean(
        string="Validacion estado agotada",
        default=False,
        index=True,
        readonly=True,
    )
    status_validation_error = fields.Text(
        string="Ultimo error validacion estado",
        readonly=True,
    )
    last_sync_at = fields.Datetime(index=True)
    raw_payload = fields.Text()

    _sql_constraints = [
        ("pf_gateway_transfer_external_id_uniq", "unique(external_id)", "El external_id de la transferencia del gateway debe ser único."),
    ]

    @api.depends("origin_id", "payment_id", "movement_nature")
    def _compute_name(self):
        for record in self:
            label = record.origin_id or record.payment_id or record.external_id
            if record.movement_nature:
                record.name = f"[{record.movement_nature}] {label}"
            else:
                record.name = label

    @api.depends(
        "source_address",
        "destination_address",
        "source_bank_account_id",
        "source_bank_account_id.app",
        "destination_bank_account_id",
        "destination_bank_account_id.app",
    )
    def _compute_address_displays(self):
        account_model = self.env["pf.gateway.bank.account"].sudo()
        unresolved_addresses = {
            address
            for record in self
            for address in (record.source_address, record.destination_address)
            if address
        }
        accounts_by_cvu = {}
        if unresolved_addresses:
            accounts = account_model.search([("cvu_cbu", "in", list(unresolved_addresses))])
            accounts_by_cvu = {account.cvu_cbu: account for account in accounts}

        for record in self:
            record.source_address_display = record._address_badge_html(
                record.source_address,
                record.source_bank_account_id,
                accounts_by_cvu.get(record.source_address),
            )
            record.destination_address_display = record._address_badge_html(
                record.destination_address,
                record.destination_bank_account_id,
                accounts_by_cvu.get(record.destination_address),
            )

    def _address_badge_html(self, address, linked_account, fallback_account):
        account = linked_account or fallback_account
        app = (account.app or "").strip().lower() if account else ""
        if app:
            code = self._wallet_code(app)
            css_class = "pf_transfer_wallet_%s" % app.replace(" ", "_").replace("-", "_")
        elif address:
            code = "EXT"
            css_class = "pf_transfer_wallet_external"
        else:
            code = "?"
            css_class = "pf_transfer_wallet_unknown"

        label = escape(address or "-")
        return (
            "<span class='pf_transfer_address_badge %s'>%s</span>"
            "<span class='pf_transfer_address_value'>%s</span>"
        ) % (escape(css_class), escape(code), label)

    def _wallet_code(self, app):
        codes = {
            "pagoflex": "PF",
            "sivep": "SV",
        }
        return codes.get(app, app[:3].upper() if app else "?")

    def _app_key(self, app_name):
        return (app_name or "").strip().lower()

    def _bank_accounts_for_app_key(self, app_key):
        app_key = self._app_key(app_key)
        if not app_key:
            return self.env["pf.gateway.bank.account"]
        app_keys = self._equivalent_app_keys(app_key)
        return self.env["pf.gateway.bank.account"].sudo().search([("app", "!=", False)]).filtered(
            lambda account: self._app_key(account.app) in app_keys
        )

    def _equivalent_app_keys(self, app_key):
        app_key = self._app_key(app_key)
        equivalents = {
            "sivep": {"sivep"},
        }
        return equivalents.get(app_key, {app_key})

    def _compute_dashboard_filter_flags(self):
        commission_accounts = self.env["pf.gateway.dashboard.app.config"].sudo().search(
            [("active", "=", True), ("commission_bank_account_id", "!=", False)]
        ).mapped("commission_bank_account_id")
        commission_account_ids = set(commission_accounts.ids)
        for record in self:
            record.is_external_incoming_transfer = record._is_external_incoming_transfer_record()
            record.is_external_outgoing_transfer = record._is_external_outgoing_transfer_record()
            record.is_dashboard_commission_account_transfer = bool(
                record.source_bank_account_id.id in commission_account_ids
                or record.destination_bank_account_id.id in commission_account_ids
            )
            record.is_pagoflex_wallet_transfer = record._is_wallet_transfer_for_app("pagoflex")
            record.is_sivep_wallet_transfer = record._is_wallet_transfer_for_app("sivep")

    def _is_external_incoming_transfer_record(self):
        self.ensure_one()
        if self.movement_nature != "TRANSFER":
            return False
        if (self.status or "").upper() == "FAILED":
            return False
        if not self.source_address:
            return False
        account_cvus = set(
            self.env["pf.gateway.bank.account"]
            .sudo()
            .search([("cvu_cbu", "!=", False)])
            .mapped("cvu_cbu")
        )
        source_is_wallet = bool(self.source_bank_account_id) or self.source_address in account_cvus
        destination_is_wallet = bool(self.destination_bank_account_id) or self.destination_address in account_cvus
        return destination_is_wallet and not source_is_wallet

    def _is_internal_transfer_record(self):
        self.ensure_one()
        if self.movement_nature != "TRANSFER":
            return False
        account_cvus = set(
            self.env["pf.gateway.bank.account"]
            .sudo()
            .search([("cvu_cbu", "!=", False)])
            .mapped("cvu_cbu")
        )
        source_is_wallet = bool(self.source_bank_account_id) or self.source_address in account_cvus
        destination_is_wallet = bool(self.destination_bank_account_id) or self.destination_address in account_cvus
        return source_is_wallet and destination_is_wallet

    def _is_external_outgoing_transfer_record(self):
        self.ensure_one()
        if self.movement_nature != "TRANSFER":
            return False
        if (self.status or "").upper() == "FAILED":
            return False
        if not self.destination_address:
            return False
        account_cvus = set(
            self.env["pf.gateway.bank.account"]
            .sudo()
            .search([("cvu_cbu", "!=", False)])
            .mapped("cvu_cbu")
        )
        source_is_wallet = bool(self.source_bank_account_id) or self.source_address in account_cvus
        destination_is_wallet = bool(self.destination_bank_account_id) or self.destination_address in account_cvus
        return source_is_wallet and not destination_is_wallet

    def _is_positive_boolean_search(self, operator, value):
        values = value if isinstance(value, (list, tuple, set)) else [value]
        bool_values = {bool(item) for item in values}
        if operator in ("=", "=="):
            return bool(value)
        if operator in ("!=", "<>"):
            return not bool(value)
        if operator == "in":
            if bool_values == {True}:
                return True
            if bool_values == {False}:
                return False
            return None
        if operator == "not in":
            if bool_values == {False}:
                return True
            if bool_values == {True}:
                return False
            return None
        return False

    def _search_is_external_incoming_transfer(self, operator, value):
        positive = self._is_positive_boolean_search(operator, value)
        if positive is None:
            return []
        account_cvus = set(
            self.env["pf.gateway.bank.account"]
            .sudo()
            .search([("cvu_cbu", "!=", False)])
            .mapped("cvu_cbu")
        )
        candidates = self.sudo().search([
            ("movement_nature", "=", "TRANSFER"),
            ("source_address", "!=", False),
        ])
        external_incoming_ids = candidates.filtered(
            lambda transfer: (transfer.status or "").upper() != "FAILED"
            and not transfer.source_bank_account_id
            and transfer.source_address not in account_cvus
            and (transfer.destination_bank_account_id or transfer.destination_address in account_cvus)
        ).ids
        return [("id", "in", external_incoming_ids)] if positive else [("id", "not in", external_incoming_ids)]

    def _search_is_external_outgoing_transfer(self, operator, value):
        positive = self._is_positive_boolean_search(operator, value)
        if positive is None:
            return []
        account_cvus = set(
            self.env["pf.gateway.bank.account"]
            .sudo()
            .search([("cvu_cbu", "!=", False)])
            .mapped("cvu_cbu")
        )
        candidates = self.sudo().search([
            ("movement_nature", "=", "TRANSFER"),
            ("destination_address", "!=", False),
        ])
        external_outgoing_ids = candidates.filtered(
            lambda transfer: (transfer.status or "").upper() != "FAILED"
            and (transfer.source_bank_account_id or transfer.source_address in account_cvus)
            and not transfer.destination_bank_account_id
            and transfer.destination_address not in account_cvus
        ).ids
        return [("id", "in", external_outgoing_ids)] if positive else [("id", "not in", external_outgoing_ids)]

    def _search_is_dashboard_commission_account_transfer(self, operator, value):
        positive = self._is_positive_boolean_search(operator, value)
        if positive is None:
            return []
        account_ids = self.env["pf.gateway.dashboard.app.config"].sudo().search(
            [("active", "=", True), ("commission_bank_account_id", "!=", False)]
        ).mapped("commission_bank_account_id").ids
        if not account_ids:
            return [("id", "=", 0)] if positive else []
        positive_domain = [
            "|",
            ("source_bank_account_id", "in", account_ids),
            ("destination_bank_account_id", "in", account_ids),
        ]
        if positive:
            return positive_domain
        return [
            ("source_bank_account_id", "not in", account_ids),
            ("destination_bank_account_id", "not in", account_ids),
        ]

    def _is_wallet_transfer_for_app(self, app_key):
        self.ensure_one()
        app_key = self._app_key(app_key)
        if not app_key:
            return False
        app_keys = self._equivalent_app_keys(app_key)
        if self._app_key(self.source_bank_account_id.app) in app_keys:
            return True
        if self._app_key(self.destination_bank_account_id.app) in app_keys:
            return True
        account_cvus = set(self._bank_accounts_for_app_key(app_key).mapped("cvu_cbu"))
        return bool(
            (self.source_address and self.source_address in account_cvus)
            or (self.destination_address and self.destination_address in account_cvus)
        )

    def _search_wallet_transfer_for_app(self, app_key, operator, value):
        positive = self._is_positive_boolean_search(operator, value)
        if positive is None:
            return []
        accounts = self._bank_accounts_for_app_key(app_key)
        account_ids = accounts.ids
        account_cvus = [cvu for cvu in accounts.mapped("cvu_cbu") if cvu]
        candidates = self.sudo().search([
            "|", "|", "|",
            ("source_bank_account_id", "in", account_ids or [0]),
            ("destination_bank_account_id", "in", account_ids or [0]),
            ("source_address", "in", account_cvus or ["__none__"]),
            ("destination_address", "in", account_cvus or ["__none__"]),
        ])
        return [("id", "in", candidates.ids)] if positive else [("id", "not in", candidates.ids)]

    def _search_is_pagoflex_wallet_transfer(self, operator, value):
        return self._search_wallet_transfer_for_app("pagoflex", operator, value)

    def _search_is_sivep_wallet_transfer(self, operator, value):
        return self._search_wallet_transfer_for_app("sivep", operator, value)

    def action_sync_transfers(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def action_sync_transfers_full(self):
        self.sync_from_gateway(mode="manual", sync_mode="full")
        return True

    def action_query_by_origin_id(self):
        self.ensure_one()
        response = self._query_bank_by_origin_id()
        self._update_bank_business_data_from_response(response)
        return self._open_response_wizard(_("Consulta por Origin ID"), response)

    def action_query_by_connector_id(self):
        self.ensure_one()
        if not self.connector_id:
            raise UserError(_("Esta transferencia no tiene Connector ID asignado."))
        response = self._query_bank_by_connector_id()
        self._update_bank_business_data_from_response(response)
        return self._open_response_wizard(_("Consulta por Connector ID (Coelsa)"), response)

    def _open_response_wizard(self, title, response):
        response_text = self._payload_to_text(response)
        self.sudo().write({"connector_response": response_text})
        wizard = self.env["pf.gateway.transfer.response.wizard"].create({
            "title": title,
            "response_text": response_text,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "pf.gateway.transfer.response.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "name": title,
        }

    def _query_bank_by_origin_id(self):
        self.ensure_one()
        if not self.origin_id:
            raise UserError(_("Esta transferencia no tiene Origin ID asignado."))
        return self._gateway_request_json(
            "GET", f"/admin/gateway/bdc/direct/transfers/by-origin-id/{self.origin_id}"
        )

    def _query_bank_by_connector_id(self):
        self.ensure_one()
        if not self.connector_id:
            raise UserError(_("Esta transferencia no tiene Connector ID asignado."))
        return self._gateway_request_json(
            "GET", f"/admin/gateway/bdc/direct/transfers/by-id-coelsa/{self.connector_id}"
        )

    def _iter_bank_response_dicts(self, payload):
        if isinstance(payload, dict):
            yield payload
            for value in payload.values():
                yield from self._iter_bank_response_dicts(value)
        elif isinstance(payload, list):
            for value in payload:
                yield from self._iter_bank_response_dicts(value)

    def _extract_bank_response_value(self, response, field_names):
        normalized_names = {name.replace("_", "").replace(" ", "").lower() for name in field_names}
        for item in self._iter_bank_response_dicts(response):
            for key, value in item.items():
                normalized_key = str(key).replace("_", "").replace(" ", "").lower()
                if normalized_key in normalized_names and value not in (None, ""):
                    return value
        return False

    def _extract_business_date_from_bank_response(self, response):
        field_names = (
            "fecha_negocio",
            "fecha negocio",
            "fechaNegocio",
            "fehaNegocio",
            "business_date",
            "businessDate",
            "operation_date",
            "operationDate",
            "fecha_operacion",
            "fechaOperacion",
            "fecha_compensacion",
            "fechaCompensacion",
            "fecha_liquidacion",
            "fechaLiquidacion",
            "fecha",
        )
        for field_name in field_names:
            value = self._extract_bank_response_value(response, (field_name,))
            date_value = self._coerce_date(value, field_name=field_name)
            if date_value:
                return date_value
        return False

    def _extract_connector_id_from_bank_response(self, response):
        value = self._extract_bank_response_value(
            response,
            (
                "idCoelsa",
                "id_coelsa",
                "coelsa_id",
                "idCoelsaTransferencia",
                "connector_id",
            ),
        )
        if not value:
            for item in self._iter_bank_response_dicts(response):
                operacion = item.get("operacion") if isinstance(item.get("operacion"), dict) else {}
                if operacion.get("id"):
                    value = operacion.get("id")
                    break
                response_data = item.get("response") if isinstance(item.get("response"), dict) else {}
                objeto = response_data.get("objeto") if isinstance(response_data.get("objeto"), dict) else {}
                if objeto.get("id"):
                    value = objeto.get("id")
                    break
        return str(value).strip() if value else False

    def _extract_status_from_bank_response(self, response):
        if not isinstance(response, dict):
            return False

        candidates = [
            response,
            response.get("transfer"),
            response.get("data"),
            response.get("result"),
            response.get("transaction"),
            response.get("payment"),
        ]
        for candidate in candidates:
            if isinstance(candidate, dict):
                status = candidate.get("estado") or candidate.get("status") or candidate.get("state")
                if isinstance(status, dict):
                    status = status.get("codigo") or status.get("code") or status.get("descripcion")
                if status:
                    status = str(status).strip().upper()
                    if status == "EN CURSO":
                        return "AUTHORIZED"
                    return status
        return False

    def _target_status_from_bank_response(self, response):
        status = self._extract_status_from_bank_response(response)
        return status or "FAILED"

    def _update_bank_business_data_from_response(self, response):
        self.ensure_one()
        values = {
            "connector_response": self._payload_to_text(response),
            "business_data_last_check_at": fields.Datetime.now(),
            "last_sync_at": fields.Datetime.now(),
        }
        business_date = self._extract_business_date_from_bank_response(response)
        if business_date:
            values["fecha_negocio"] = business_date
        connector_id = self._extract_connector_id_from_bank_response(response)
        connector_updated = bool(connector_id and not self.connector_id)
        if connector_updated:
            values["connector_id"] = connector_id
        self.with_context(skip_gateway_status_push=True).write(values)
        return bool(business_date), connector_updated

    def _business_date_from_item(self, item, transaction_at=False):
        for field_name in ("fecha_negocio", "fechaNegocio", "fehaNegocio", "business_date", "businessDate", "operation_date", "operationDate"):
            date_value = self._coerce_date(item.get(field_name), field_name=field_name)
            if date_value:
                return date_value
        extra_metadata = item.get("extra_metadata")
        if isinstance(extra_metadata, dict):
            for field_name in ("fecha_negocio", "fecha negocio", "fechaNegocio", "fehaNegocio", "business_date", "businessDate", "operation_date", "operationDate"):
                date_value = self._coerce_date(extra_metadata.get(field_name), field_name=field_name)
                if date_value:
                    return date_value
        return False

    @api.model
    def _expire_pending_status_validation_records(self, max_attempts):
        self.env.cr.execute(
            """
            UPDATE pf_gateway_transfer
               SET status_validation_exhausted = TRUE
             WHERE active IS TRUE
               AND origin_id IS NOT NULL
               AND status_validation_exhausted IS NOT TRUE
               AND (
                    COALESCE(status_validation_attempts, 0) >= %s
                    OR UPPER(TRIM(COALESCE(status, ''))) IN ('COMPLETED', 'FAILED')
               )
            """,
            [max_attempts],
        )
        return self.env.cr.rowcount

    @api.model
    def cron_validate_pending_transfer_statuses(self, limit=10):
        transfer_model = self.sudo()
        params = self.env["ir.config_parameter"].sudo()
        try:
            max_attempts = int(params.get_param("pagoflex_wallet_gateway.pending_status_max_attempts", "5") or 5)
        except ValueError:
            max_attempts = 5
        try:
            cooldown_minutes = int(params.get_param("pagoflex_wallet_gateway.pending_status_cooldown_minutes", "30") or 30)
        except ValueError:
            cooldown_minutes = 30
        try:
            max_days = int(params.get_param("pagoflex_wallet_gateway.pending_status_max_days", "3") or 3)
        except ValueError:
            max_days = 3
            
        max_attempts = max(1, max_attempts)
        cooldown_minutes = max(0, cooldown_minutes)
        max_days = max(1, max_days)
        
        now = fields.Datetime.now()
        cooldown_limit = fields.Datetime.subtract(now, minutes=cooldown_minutes) if cooldown_minutes else now
        time_limit = fields.Datetime.subtract(now, days=max_days)
        expired_before_search = transfer_model._expire_pending_status_validation_records(max_attempts)
        transfers = transfer_model.search(
            [
                ("active", "=", True),
                ("origin_id", "!=", False),
                ("is_external_outgoing_transfer", "=", True),
                ("transaction_at", ">=", time_limit),
                ("status_validation_exhausted", "=", False),
                "|",
                ("status_validation_attempts", "=", False),
                ("status_validation_attempts", "<", max_attempts),
                "|",
                ("status_validation_last_at", "=", False),
                ("status_validation_last_at", "<=", cooldown_limit),
                "|",
                ("status", "=", False),
                ("status", "not in", ["COMPLETED", "FAILED"]),
            ],
            order="transaction_at desc, id desc",
            limit=limit,
        )
        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": _("Validar estado de transferencias pendientes"),
                "resource": "transfers",
                "mode": "cron",
            }
        )
        processed = 0
        updated = 0
        errors = []
        affected_account_ids = set()
        for transfer in transfers:
            attempt_now = fields.Datetime.now()
            attempts = (transfer.status_validation_attempts or 0) + 1
            try:
                response = transfer._query_bank_by_origin_id()
                response_text = transfer._payload_to_text(response)
                _logger.info(
                    "Bank transfer status response origin_id=%s transfer_id=%s external_id=%s response=%s",
                    transfer.origin_id,
                    transfer.id,
                    transfer.external_id,
                    response_text,
                )
                target_status = transfer._target_status_from_bank_response(response)
                target_status = (target_status or "").strip().upper()
                current_status = (transfer.status or "").strip().upper()
                exhausted = target_status in ("COMPLETED", "FAILED") or attempts >= max_attempts
                values = {
                    "connector_response": response_text,
                    "last_sync_at": attempt_now,
                    "status_validation_attempts": attempts,
                    "status_validation_last_at": attempt_now,
                    "status_validation_exhausted": exhausted,
                    "status_validation_error": False,
                }
                if target_status and target_status != (transfer.status or "").strip().upper():
                    values["status"] = target_status
                    if target_status == "COMPLETED":
                        if transfer.source_bank_account_id:
                            affected_account_ids.add(transfer.source_bank_account_id.id)
                        if transfer.destination_bank_account_id:
                            affected_account_ids.add(transfer.destination_bank_account_id.id)
                    updated += 1
                elif current_status in ("COMPLETED", "FAILED"):
                    values["status_validation_exhausted"] = True
                transfer.with_context(skip_gateway_status_push=True).write(values)
                processed += 1
            except Exception as exc:
                exhausted = attempts >= max_attempts
                transfer.with_context(skip_gateway_status_push=True).write(
                    {
                        "last_sync_at": attempt_now,
                        "status_validation_attempts": attempts,
                        "status_validation_last_at": attempt_now,
                        "status_validation_exhausted": exhausted,
                        "status_validation_error": str(exc),
                    }
                )
                errors.append("%s: %s" % (transfer.origin_id or transfer.id, exc))

            self.env.cr.commit()

        status = "failed" if errors and not processed else "success"
        message = _("Transferencias validadas: %(processed)s. Estados actualizados: %(updated)s. Validaciones agotadas antes de consultar: %(expired)s. Intentos maximos: %(max_attempts)s. Enfriamiento: %(cooldown)s min.") % {
            "processed": processed,
            "updated": updated,
            "expired": expired_before_search,
            "max_attempts": max_attempts,
            "cooldown": cooldown_minutes,
        }
        if errors:
            message = "%s %s" % (message, _("Errores: %s") % "; ".join(errors[:5]))
        log.write(
            {
                "status": status,
                "finished_at": fields.Datetime.now(),
                "records_processed": processed,
                "message": message,
                "error_detail": "\n".join(errors) if errors else False,
            }
        )
        if affected_account_ids:
            accounts = self.env["pf.gateway.bank.account"].sudo().browse(list(affected_account_ids)).exists()
            if accounts:
                accounts._refresh_balance_from_gateway(auto_commit=True)
        return processed

    @api.model
    def cron_update_completed_transfer_business_data(self):
        transfer_model = self.sudo()
        params = self.env["ir.config_parameter"].sudo()
        try:
            batch_size = int(params.get_param("pagoflex_wallet_gateway.completed_business_data_batch_size", "50") or 50)
        except ValueError:
            batch_size = 50
        try:
            progress_every = int(params.get_param("pagoflex_wallet_gateway.completed_business_data_progress_every", "10") or 10)
        except ValueError:
            progress_every = 10
        batch_size = max(1, batch_size)
        progress_every = max(1, progress_every)
        domain = [
            ("active", "=", True),
            ("status", "=", "COMPLETED"),
            ("business_data_last_check_at", "=", False),
            "|",
            ("connector_id", "!=", False),
            ("origin_id", "!=", False),
        ]
        candidate_limit = batch_size * 5
        candidate_transfers = transfer_model.search(
            domain,
            order="transaction_at asc, id asc",
            limit=candidate_limit,
        )
        transfers = candidate_transfers.filtered(lambda transfer: not transfer._is_internal_transfer_record())[:batch_size]
        pending_before = transfer_model.search_count(domain)
        skipped_internal = len(candidate_transfers) - len(transfers)
        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": _("Actualizar fecha negocio de transferencias completadas"),
                "resource": "transfers",
                "mode": "manual",
                "message": _("Iniciando. Pendientes candidatos: %(pending)s. Lote: %(batch)s. Internas omitidas en preselección: %(skipped_internal)s.") % {
                    "pending": pending_before,
                    "batch": len(transfers),
                    "skipped_internal": skipped_internal,
                },
            }
        )
        self.env.cr.commit()
        processed = 0
        attempted = 0
        date_updated = 0
        connector_updated = 0
        skipped = 0
        errors = []
        for transfer in transfers:
            attempted += 1
            try:
                if transfer.connector_id:
                    response = transfer._query_bank_by_connector_id()
                elif transfer.origin_id:
                    response = transfer._query_bank_by_origin_id()
                else:
                    skipped += 1
                    continue
                has_business_date, has_connector_update = transfer._update_bank_business_data_from_response(response)
                if has_business_date:
                    date_updated += 1
                if has_connector_update:
                    connector_updated += 1
                processed += 1
            except Exception as exc:
                errors.append("%s: %s" % (transfer.origin_id or transfer.connector_id or transfer.id, exc))
                _logger.exception(
                    "Error actualizando fecha negocio de transferencia completed id=%s origin_id=%s connector_id=%s",
                    transfer.id,
                    transfer.origin_id,
                    transfer.connector_id,
                )
            if attempted % progress_every == 0:
                log.write(
                    {
                        "records_processed": processed,
                        "message": _(
                            "En progreso. Pendientes iniciales: %(pending)s. Intentadas: %(attempted)s/%(batch)s. Consultadas: %(processed)s. Fecha negocio actualizada: %(date_updated)s. ID Coelsa completado: %(connector_updated)s. Errores: %(errors)s."
                        ) % {
                            "pending": pending_before,
                            "attempted": attempted,
                            "processed": processed,
                            "batch": len(transfers),
                            "date_updated": date_updated,
                            "connector_updated": connector_updated,
                            "errors": len(errors),
                        },
                        "error_detail": "\n".join(errors) if errors else False,
                    }
                )
                self.env.cr.commit()

        status = "failed" if errors and not processed else "success"
        pending_after = transfer_model.search_count(domain)
        message = _(
            "Transferencias consultadas: %(processed)s/%(batch)s. Pendientes candidatos antes: %(pending_before)s. Pendientes candidatos despues: %(pending_after)s. Fecha negocio actualizada: %(date_updated)s. ID Coelsa completado: %(connector_updated)s. Omitidas: %(skipped)s. Internas omitidas en preselección: %(skipped_internal)s."
        ) % {
            "processed": processed,
            "batch": len(transfers),
            "pending_before": pending_before,
            "pending_after": pending_after,
            "date_updated": date_updated,
            "connector_updated": connector_updated,
            "skipped": skipped,
            "skipped_internal": skipped_internal,
        }
        if errors:
            message = "%s %s" % (message, _("Errores: %s") % len(errors))
        log.write(
            {
                "status": status,
                "finished_at": fields.Datetime.now(),
                "records_processed": processed,
                "message": message,
                "error_detail": "\n".join(errors) if errors else False,
            }
        )
        return processed

    def _push_status_to_gateway(self, status):
        self.ensure_one()
        if not self.external_id:
            raise UserError(_("No se puede actualizar estado en gateway sin external_id."))

        response = self._gateway_request_json(
            "PATCH",
            f"/admin/gateway/transfers/{self.external_id}/status",
            payload={"status": status},
        )
        if not isinstance(response, dict):
            raise UserError(_("El gateway devolvió una respuesta inválida al actualizar el estado."))

        transfer_data = response.get("transfer") if isinstance(response.get("transfer"), dict) else response
        confirmed_status = transfer_data.get("status") if isinstance(transfer_data, dict) else None
        if confirmed_status and str(confirmed_status).upper() != str(status).upper():
            raise UserError(
                _("El gateway confirmó un estado distinto. Enviado: %(sent)s. Recibido: %(received)s.")
                % {"sent": status, "received": confirmed_status}
            )
        return response

    def write(self, vals):
        if self.env.context.get("skip_gateway_status_push"):
            return super().write(vals)

        if "status" not in vals:
            return super().write(vals)

        new_status = vals.get("status")
        if not new_status:
            raise UserError(_("El estado no puede estar vacío."))

        for record in self:
            record._push_status_to_gateway(new_status)

        result = super().write(vals)
        if hasattr(self.env.user, "notify_success"):
            self.env.user.notify_success(message=_("Estado actualizado correctamente en gateway."))
        return result

    def _resolve_transfer_account(self, account_external_id=None, address=None):
        account_model = self.env["pf.gateway.bank.account"]
        account = account_model.browse()
        if account_external_id:
            account = account_model.search([("external_id", "=", str(account_external_id))], limit=1)
        if not account and address:
            account = account_model.search([("cvu_cbu", "=", address)], limit=1)
        return account

    def _transfer_link_values(self, source_account, destination_account):
        return {
            "source_bank_account_id": source_account.id,
            "destination_bank_account_id": destination_account.id,
            "source_user_id": source_account.gateway_user_id.id,
            "destination_user_id": destination_account.gateway_user_id.id,
        }

    def _transfer_link_values_from_item(self, item):
        source_account = self._resolve_transfer_account(
            account_external_id=item.get("source_account_id"),
            address=item.get("source_address"),
        )
        destination_account = self._resolve_transfer_account(
            account_external_id=item.get("destination_account_id"),
            address=item.get("destination_address"),
        )
        return self._transfer_link_values(source_account, destination_account)

    def _transfer_payload_dict(self, raw_payload):
        if not raw_payload:
            return {}
        if isinstance(raw_payload, dict):
            return raw_payload
        try:
            payload = json.loads(raw_payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _relink_orphan_transfers(self):
        orphan_domain = [
            "|",
            "|",
            ("source_bank_account_id", "=", False),
            ("destination_bank_account_id", "=", False),
            "|",
            ("source_user_id", "=", False),
            ("destination_user_id", "=", False),
        ]
        orphan_transfers = self.search(orphan_domain)
        relinked = 0
        for transfer in orphan_transfers:
            payload = self._transfer_payload_dict(transfer.raw_payload)
            source_account = transfer.source_bank_account_id or self._resolve_transfer_account(
                account_external_id=payload.get("source_account_id"),
                address=transfer.source_address,
            )
            destination_account = transfer.destination_bank_account_id or self._resolve_transfer_account(
                account_external_id=payload.get("destination_account_id"),
                address=transfer.destination_address,
            )
            values = self._transfer_link_values(source_account, destination_account)
            changed_values = {
                field_name: value
                for field_name, value in values.items()
                if transfer[field_name].id != value
            }
            if changed_values:
                transfer.with_context(skip_gateway_status_push=True).write(changed_values)
                relinked += 1
        return relinked

    @api.model
    def cron_relink_orphan_transfers(self):
        relinked = self.sudo()._relink_orphan_transfers()
        _logger.info("[cron_relink_orphan_transfers] Transferencias reenlazadas: %s", relinked)
        return relinked

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        transfer_model = self.sudo()
        updated_since = None
        if sync_mode == "incremental":
            updated_since = transfer_model.search([], order="source_updated_at desc", limit=1).source_updated_at

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar transferencias ({sync_mode})",
                "resource": "transfers",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            affected_account_ids = set()
            items = self._gateway_paginated_get("/admin/gateway/transfers", updated_since=updated_since)
            for item in items:
                transaction_at = self._coerce_datetime(item.get("transaction_at"), field_name="transaction_at")
                business_date = self._business_date_from_item(item)
                values = {
                    "external_id": str(item.get("id")),
                    "active": True,
                    "payment_id": item.get("payment_id"),
                    "origin_id": item.get("origin_id"),
                    "status": item.get("status"),
                    "movement_nature": item.get("movement_nature"),
                    "amount": item.get("amount") or 0.0,
                    "currency": item.get("currency"),
                    "concept": item.get("concept"),
                    "description": item.get("description"),
                    "connector_id": item.get("connector_id"),
                    "source_address": item.get("source_address"),
                    "source_address_type": item.get("source_address_type"),
                    "source_owner_id_type": item.get("source_owner_id_type"),
                    "source_owner_id": item.get("source_owner_id"),
                    "source_owner_name": item.get("source_owner_name"),
                    "destination_address": item.get("destination_address"),
                    "destination_address_type": item.get("destination_address_type"),
                    "destination_owner_id_type": item.get("destination_owner_id_type"),
                    "destination_owner_id": item.get("destination_owner_id"),
                    "destination_owner_name": item.get("destination_owner_name"),
                    "extra_metadata": self._payload_to_text(item.get("extra_metadata")),
                    "connector_response": self._payload_to_text(item.get("connector_response")),
                    "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
                    "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
                    "transaction_at": transaction_at,
                    "last_sync_at": fields.Datetime.now(),
                    "raw_payload": self._payload_to_text(item),
                }
                values.update(self._transfer_link_values_from_item(item))
                if values.get("source_bank_account_id"):
                    affected_account_ids.add(values["source_bank_account_id"])
                if values.get("destination_bank_account_id"):
                    affected_account_ids.add(values["destination_bank_account_id"])
                    
                record = transfer_model.search([("external_id", "=", values["external_id"])], limit=1)
                if business_date:
                    values["fecha_negocio"] = business_date
                if record:
                    record.with_context(skip_gateway_status_push=True).write(values)
                else:
                    transfer_model.create(values)

            relinked = transfer_model._relink_orphan_transfers()
            
            if affected_account_ids:
                accounts = self.env["pf.gateway.bank.account"].sudo().browse(list(affected_account_ids)).exists()
                if accounts:
                    accounts._refresh_balance_from_gateway(auto_commit=True)
                    
            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Transferencias sincronizadas: {len(items)}. Reenlazadas: {relinked}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de transferencias fallo.",
                }
            )
            if job:
                job.write(
                    {
                        "last_run_at": fields.Datetime.now(),
                        "last_status": "failed",
                        "last_message": str(exc),
                    }
                )
            raise
