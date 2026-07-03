import logging
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayBankAccount(models.Model):
    _name = "pf.gateway.bank.account"
    _description = "Cuenta bancaria de PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(required=True, index=True)
    origin_id = fields.Integer(index=True)
    gateway_user_id = fields.Many2one("pf.gateway.user", string="Usuario del gateway", ondelete="set null", index=True)
    cvu_cbu = fields.Char(index=True)
    account_type = fields.Char()
    alias = fields.Char(index=True)
    status = fields.Selection(
        [
            ("active", "Activa"),
            ("suspended", "Suspendida"),
            ("blocked", "Bloqueada"),
        ],
        index=True,
    )
    is_primary = fields.Boolean()
    bdc_account_id = fields.Char(index=True)
    app = fields.Char(index=True)
    currency = fields.Char()
    balance = fields.Monetary(currency_field="currency_id")
    balance_sync_status = fields.Selection(
        [
            ("never", "Nunca consultado"),
            ("ok", "Actualizado"),
            ("not_found", "No encontrada en gateway"),
            ("no_balance", "Sin saldo en respuesta"),
            ("error", "Error al consultar"),
        ],
        default="never",
        index=True,
        string="Estado consulta saldo",
    )
    balance_sync_message = fields.Char(string="Detalle consulta saldo")
    balance_last_check_at = fields.Datetime(string="Ultima consulta saldo", index=True)
    currency_id = fields.Many2one("res.currency", string="Moneda de Odoo")
    extra_metadata = fields.Text()
    source_created_at = fields.Datetime()
    source_updated_at = fields.Datetime(index=True)
    last_sync_at = fields.Datetime(index=True)
    raw_payload = fields.Text()
    outgoing_transfer_ids = fields.One2many("pf.gateway.transfer", "source_bank_account_id", string="Transferencias salientes")
    incoming_transfer_ids = fields.One2many("pf.gateway.transfer", "destination_bank_account_id", string="Transferencias entrantes")
    user_display_name = fields.Char(
        string="Usuario",
        compute="_compute_user_display_name",
        store=False,
    )

    _sql_constraints = [
        ("pf_gateway_bank_account_external_id_uniq", "unique(external_id)", "El external_id de la cuenta bancaria del gateway debe ser único."),
    ]
    _BALANCE_REFRESH_QUEUE_PARAM = "pagoflex_wallet_gateway.balance_refresh_account_ids"
    _BALANCE_REFRESH_CRON_CODE = "model._cron_refresh_balances_reusable()"
    _BALANCE_REFRESH_CRON_NAME = "PagoFlex Refrescar saldos bancarios"
    _BANK_MOVEMENT_QUERY_CBU_PARAM = "pagoflex_wallet_gateway.bank_movement_query_cbu"

    @api.depends("cvu_cbu", "alias", "origin_id")
    def _compute_name(self):
        for record in self:
            record.name = record.cvu_cbu or record.alias or str(record.origin_id or record.external_id)

    def _resolve_currency(self, currency_code):
        if not currency_code:
            return False
        return self.env["res.currency"].search([("name", "=", currency_code)], limit=1).id

    def _normalize_status(self, value):
        status = (value or "").strip().lower()
        if status in {"active", "suspended"}:
            return status
        return False

    def action_sync_bank_accounts(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    @api.model
    def _name_search(self, name="", domain=None, operator="ilike", limit=100, order=None):
        domain = list(domain or [])

        # Remover cualquier filtro por app para permitir carga/manual de datos sin restricción por aplicación.
        domain = [
            d for d in domain
            if not (isinstance(d, (list, tuple)) and len(d) >= 1 and d[0] == "app")
        ]

        # Siempre inyectar status=active si no está presente
        if not any(isinstance(d, (list, tuple)) and len(d) >= 3 and d[0] == "status" for d in domain):
            domain.append(("status", "=", "active"))
        _logger.debug(
            "[BankAccount._name_search] name=%r domain=%s operator=%r limit=%s",
            name,
            domain,
            operator,
            limit,
        )
        result = super()._name_search(name=name, domain=domain, operator=operator, limit=limit, order=order)
        _logger.debug("[BankAccount._name_search] → %s resultados", len(result) if result is not None else "None")
        return result


    def _balance_request_payload(self):
        self.ensure_one()
        return {
            "app": self.app,
            "cvu_cbu": self.cvu_cbu,
        }

    def _sub_account_patch_payload(self, vals):
        payload = {}
        if "status" in vals:
            normalized = self._normalize_status(vals.get("status"))
            if normalized:
                payload["status"] = normalized.upper()
        if "alias" in vals:
            payload["alias"] = vals.get("alias")
        return payload

    def _push_sub_account_update(self, vals):
        self.ensure_one()
        payload = self._sub_account_patch_payload(vals)
        if not payload:
            return {}
        if not self.cvu_cbu:
            raise UserError(_("No se puede actualizar sub-cuenta en gateway sin CVU/CBU."))

        response = self._gateway_request_json(
            "PATCH",
            f"/admin/gateway/sub-account/{self.cvu_cbu}",
            payload=payload,
        )
        if not isinstance(response, dict):
            raise UserError(_("El gateway devolvió una respuesta inválida al actualizar la sub-cuenta."))
        return response

    def write(self, vals):
        if self.env.context.get("skip_gateway_sub_account_push"):
            return super().write(vals)

        push_fields = {"status", "alias"}
        if not push_fields.intersection(vals):
            return super().write(vals)

        for record in self:
            record._push_sub_account_update(vals)

        return super().write(vals)

    def _extract_balance_from_response(self, response, expected_account_id=None):
        if not isinstance(response, dict):
            return None

        candidates = [
            response,
            response.get("account") if isinstance(response.get("account"), dict) else None,
            response.get("data") if isinstance(response.get("data"), dict) else None,
        ]
        items = response.get("items")
        if isinstance(items, list):
            item_dicts = [item for item in items if isinstance(item, dict)]
            if expected_account_id:
                matching_items = [
                    item
                    for item in item_dicts
                    if str(item.get("account_id") or item.get("id") or "") == str(expected_account_id)
                ]
                if matching_items:
                    candidates.extend(matching_items)
                candidates.extend(item for item in item_dicts if item not in matching_items)
            else:
                candidates.extend(item_dicts)
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in ("balance", "current_balance", "available_balance"):
                value = candidate.get(key)
                if value is not None:
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        text_value = str(value).replace(",", ".").strip()
                        try:
                            return float(text_value)
                        except (TypeError, ValueError):
                            continue

        return None

    def _refresh_balance_from_gateway(self):
        _logger.info("Inicio de actualización de saldo para %s cuenta(s).", len(self))
        processed = 0
        failed = 0
        for record in self:
            if not record.app or not record.cvu_cbu:
                _logger.info(
                    "Saldo omitido cuenta external_id=%s app=%s cvu_cbu=%s (faltan datos).",
                    record.external_id,
                    record.app,
                    record.cvu_cbu,
                )
                continue
            _logger.info(
                "Consultando saldo cuenta external_id=%s app=%s cvu_cbu=%s",
                record.external_id,
                record.app,
                record.cvu_cbu,
            )
            try:
                response = record._gateway_request_json(
                    "POST",
                    "/admin/gateway/bank-accounts/balance",
                    payload=record._balance_request_payload(),
                )
                balance = record._extract_balance_from_response(response, expected_account_id=record.external_id)
                if balance is None:
                    record.write(
                        {
                            "balance_sync_status": "no_balance",
                            "balance_sync_message": _("El gateway no devolvió el saldo de la cuenta."),
                            "balance_last_check_at": fields.Datetime.now(),
                        }
                    )
                    _logger.warning(
                        "Saldo no disponible cuenta external_id=%s app=%s cvu_cbu=%s response=%s",
                        record.external_id,
                        record.app,
                        record.cvu_cbu,
                        (record._payload_to_text(response) or "")[:600],
                    )
                    failed += 1
                    continue
                record.write(
                    {
                        "balance": balance,
                        "balance_sync_status": "ok",
                        "balance_sync_message": _("Saldo actualizado correctamente."),
                        "balance_last_check_at": fields.Datetime.now(),
                    }
                )
                _logger.info(
                    "Saldo actualizado cuenta external_id=%s cvu_cbu=%s balance=%s",
                    record.external_id,
                    record.cvu_cbu,
                    balance,
                )
                processed += 1
            except UserError as exc:
                message = str(exc)
                if "(404)" in message and "Cuenta no encontrada" in message:
                    record.write(
                        {
                            "balance_sync_status": "not_found",
                            "balance_sync_message": message[:255],
                            "balance_last_check_at": fields.Datetime.now(),
                        }
                    )
                    failed += 1
                    _logger.warning(
                        "Saldo no encontrado en gateway cuenta external_id=%s app=%s cvu_cbu=%s detail=%s",
                        record.external_id,
                        record.app,
                        record.cvu_cbu,
                        message,
                    )
                    continue
                record.write(
                    {
                        "balance_sync_status": "error",
                        "balance_sync_message": message[:255],
                        "balance_last_check_at": fields.Datetime.now(),
                    }
                )
                failed += 1
                _logger.exception(
                    "Error consultando saldo cuenta external_id=%s app=%s cvu_cbu=%s",
                    record.external_id,
                    record.app,
                    record.cvu_cbu,
                )
                continue
            except Exception:
                record.write(
                    {
                        "balance_sync_status": "error",
                        "balance_sync_message": _("Error inesperado al consultar saldo."),
                        "balance_last_check_at": fields.Datetime.now(),
                    }
                )
                failed += 1
                _logger.exception(
                    "Error consultando saldo cuenta external_id=%s app=%s cvu_cbu=%s",
                    record.external_id,
                    record.app,
                    record.cvu_cbu,
                )
                continue
        _logger.info(
            "Fin de actualización de saldos para cuentas bancarias. Exitosas=%s Fallidas=%s",
            processed,
            failed,
        )

    def _schedule_balance_refresh(self):
        account_ids = [account_id for account_id in self.ids if account_id]
        if not account_ids:
            return False

        queue_ids = set(self._get_balance_refresh_queue_ids())
        queue_ids.update(account_ids)
        self._set_balance_refresh_queue_ids(list(queue_ids))

        # Forzamos un flush_all aquí ANTES del bloque try..except. 
        # Esto asegura que si hubo algún error de base de datos en las escrituras 
        # anteriores (ej. constraint violations al sincronizar cuentas), la excepción 
        # salte y se propague correctamente, en lugar de ser devorada por el 
        # except Exception genérico de abajo.
        self.env.flush_all()

        try:
            # Aislar este bloque en un savepoint evita dejar la transacción
            # principal en estado abortado cuando falla SQL interno del cron.
            # Pasamos flush=False porque ya hicimos el flush arriba.
            with self.env.cr.savepoint(flush=False):
                cron = self._get_or_create_balance_refresh_cron()
                self._activate_balance_refresh_cron_sql(cron=cron)
                return cron
        except Exception:
            # Nunca bloquear la sincronizacion principal por problemas de
            # programacion del refresco de saldos en segundo plano.
            _logger.exception("No se pudo programar el refresco de saldos en segundo plano.")
            return False

    @api.model
    def _get_balance_refresh_queue_ids(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(self._BALANCE_REFRESH_QUEUE_PARAM)
        if not raw:
            return []
        try:
            values = json.loads(raw)
        except Exception:
            _logger.warning("Cola de refresco de saldos inválida en config parameter: %s", raw)
            return []

        if not isinstance(values, list):
            return []

        sanitized = []
        for value in values:
            try:
                account_id = int(value)
            except (TypeError, ValueError):
                continue
            if account_id > 0:
                sanitized.append(account_id)
        return list(dict.fromkeys(sanitized))

    @api.model
    def _set_balance_refresh_queue_ids(self, account_ids):
        sanitized = []
        for value in account_ids or []:
            try:
                account_id = int(value)
            except (TypeError, ValueError):
                continue
            if account_id > 0:
                sanitized.append(account_id)
        payload = json.dumps(sorted(set(sanitized)))
        self.env["ir.config_parameter"].sudo().set_param(self._BALANCE_REFRESH_QUEUE_PARAM, payload)

    @api.model
    def _get_or_create_balance_refresh_cron(self):
        cron_model = self.env["ir.cron"].sudo()
        model_id = self.env.ref("pagoflex_wallet_gateway.model_pf_gateway_bank_account").id

        reusable = cron_model.search(
            [
                ("model_id", "=", model_id),
                ("state", "=", "code"),
                ("code", "=", self._BALANCE_REFRESH_CRON_CODE),
            ],
            order="id asc",
            limit=1,
        )

        legacy = cron_model.search(
            [
                ("model_id", "=", model_id),
                ("state", "=", "code"),
                ("code", "like", "model._cron_refresh_balances(%"),
            ],
            order="id asc",
        )

        if reusable:
            if legacy:
                legacy.unlink()
            if reusable.active and not self._get_balance_refresh_queue_ids():
                reusable.active = False
            return reusable

        if legacy:
            cron = legacy[0]
            if len(legacy) > 1:
                (legacy - cron).unlink()
            cron.write(
                {
                    "name": self._BALANCE_REFRESH_CRON_NAME,
                    "code": self._BALANCE_REFRESH_CRON_CODE,
                    "interval_number": 1,
                    "interval_type": "minutes",
                    "active": False,
                }
            )
            return cron

        return cron_model.create(
            {
                "name": self._BALANCE_REFRESH_CRON_NAME,
                "model_id": model_id,
                "state": "code",
                "code": self._BALANCE_REFRESH_CRON_CODE,
                "interval_number": 1,
                "interval_type": "minutes",
                "active": False,
            }
        )

    @api.model
    def _cron_refresh_balances(self, account_ids=None):
        records = self.sudo().browse(account_ids or []).exists()
        records._refresh_balance_from_gateway()

    @api.model
    def _cron_refresh_balances_reusable(self):
        account_ids = self._get_balance_refresh_queue_ids()
        if not account_ids:
            self._deactivate_balance_refresh_cron_sql()
            return 0

        # Límite por ejecución para evitar el timeout del worker (default 30 cuentas)
        try:
            params = self.env["ir.config_parameter"].sudo()
            batch_size = int(params.get_param("pagoflex_wallet_gateway.balance_refresh_batch_size", "30") or 30)
        except ValueError:
            batch_size = 30
        
        batch_size = max(1, batch_size)
        batch_ids = account_ids[:batch_size]
        remaining_ids = account_ids[batch_size:]

        # Consumir el lote actual al inicio dejando los restantes en la cola.
        # Así no perdemos los ids que se agreguen mientras este cron está en ejecución.
        self._set_balance_refresh_queue_ids(remaining_ids)
        
        records = self.sudo().browse(batch_ids).exists()
        try:
            records._refresh_balance_from_gateway()
        finally:
            pending_ids = self._get_balance_refresh_queue_ids()
            if pending_ids:
                self._activate_balance_refresh_cron_sql()
            else:
                self._deactivate_balance_refresh_cron_sql()
        return len(records)

    @api.model
    def _activate_balance_refresh_cron_sql(self, cron=None):
        """Activa el cron de refresco de saldos via SQL directo para evitar
        el bloqueo ORM cuando el cron esta en ejecucion."""
        cron = cron or self.env["ir.cron"].sudo().search(
            [
                ("state", "=", "code"),
                ("code", "=", self._BALANCE_REFRESH_CRON_CODE),
                ("name", "=", self._BALANCE_REFRESH_CRON_NAME),
            ],
            order="id asc",
            limit=1,
        )
        if not cron:
            _logger.debug("Cron de refresco de saldos no encontrado para activar.")
            return

        self.env.cr.execute(
            "UPDATE ir_cron SET active = true, nextcall = %s WHERE id = %s",
            [fields.Datetime.now(), cron.id],
        )
        _logger.debug("Cron de refresco de saldos activado (id=%s).", cron.id)

    @api.model
    def _deactivate_balance_refresh_cron_sql(self):
        """Desactiva el cron de refresco de saldos via SQL directo para evitar
        el bloqueo ORM que Odoo aplica al registro del cron mientras está en ejecución."""
        cron = self.env["ir.cron"].sudo().search(
            [
                ("state", "=", "code"),
                ("code", "=", self._BALANCE_REFRESH_CRON_CODE),
                ("name", "=", self._BALANCE_REFRESH_CRON_NAME),
            ],
            order="id asc",
            limit=1,
        )
        if not cron:
            _logger.debug("Cron de refresco de saldos no encontrado para desactivar.")
            return

        self.env.cr.execute(
            "UPDATE ir_cron SET active = false WHERE id = %s AND active = true",
            [cron.id],
        )
        _logger.debug("Cron de refresco de saldos desactivado (id=%s, cola vacía).", cron.id)

    def action_refresh_balance_async(self):
        records = self
        if not records:
            active_domain = self.env.context.get("active_domain")
            domain = active_domain if isinstance(active_domain, list) else []
            if not domain:
                domain_ctx = self.env.context.get("domain")
                domain = domain_ctx if isinstance(domain_ctx, list) else []
            records = self.search(domain)

        accounts = records.filtered(lambda record: record.app and record.cvu_cbu)
        _logger.info(
            "Programando actualización de saldo para %s cuenta(s) (recordset base=%s).",
            len(accounts),
            len(records),
        )
        if not accounts:
            raise UserError(_("Las cuentas seleccionadas deben tener App y CVU/CBU para consultar saldo."))
        accounts._schedule_balance_refresh()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Consulta de saldo en segundo plano"),
                "message": _("Se programó la actualización de saldo para %(count)s cuenta(s).")
                % {"count": len(accounts)},
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_bank_movement_sync_wizard(self):
        records = self
        if not records:
            active_ids = self.env.context.get("active_ids") or []
            records = self.browse(active_ids)
        if len(records) != 1:
            raise UserError(_("Selecciona una única cuenta bancaria para consultar movimientos."))
        record = records[0]
        fixed_query_cbu = (
            self.env["ir.config_parameter"].sudo().get_param(self._BANK_MOVEMENT_QUERY_CBU_PARAM) or ""
        ).strip()
        context = {
            "default_cbu_cvu_alias": fixed_query_cbu or record.cvu_cbu or record.alias,
        }
        if not fixed_query_cbu:
            context["default_bank_account_id"] = record.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Consultar movimientos bancarios"),
            "res_model": "pf.gateway.bank.movement.sync.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="source_updated_at desc", limit=1).source_updated_at

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar cuentas bancarias ({sync_mode})",
                "resource": "bank_accounts",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            items = self._gateway_paginated_get("/admin/gateway/bank-accounts", updated_since=updated_since)
            refreshed_records = self.browse()
            for item in items:
                gateway_user = self.env["pf.gateway.user"].search([("external_id", "=", item.get("user_id"))], limit=1)
                values = {
                    "external_id": item.get("id"),
                    "active": True,
                    "origin_id": item.get("origin_id"),
                    "gateway_user_id": gateway_user.id,
                    "cvu_cbu": item.get("cvu_cbu"),
                    "account_type": item.get("account_type"),
                    "alias": item.get("alias"),
                    "status": self._normalize_status(item.get("status")),
                    "is_primary": item.get("is_primary", False),
                    "bdc_account_id": item.get("bdc_account_id"),
                    "app": item.get("app"),
                    "currency": item.get("currency"),
                    "currency_id": self._resolve_currency(item.get("currency")),
                    "extra_metadata": self._payload_to_text(item.get("extra_metadata")),
                    "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
                    "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
                    "last_sync_at": fields.Datetime.now(),
                    "raw_payload": self._payload_to_text(item),
                }
                record = self.search([("external_id", "=", values["external_id"])], limit=1)
                if record:
                    record.with_context(skip_gateway_sub_account_push=True).write(values)
                    refreshed_records |= record
                else:
                    refreshed_records |= self.create(values)

            refreshed_records.filtered(lambda record: record.app and record.cvu_cbu)._schedule_balance_refresh()

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Cuentas Bancarias sincronizadas: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de cuentas bancarias fallo.",
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

    def _compute_user_display_name(self):
        for record in self:
            user = record.gateway_user_id
            record.user_display_name = user.gateway_display_name or user.full_name or user.name or user.email or user.external_id or "-"

    def name_get(self):
        result = []
        for record in self:
            user = record.gateway_user_id
            user_name = user.gateway_display_name or user.full_name or user.name or user.email or user.external_id or "-"
            label = f"{user_name} - {record.cvu_cbu}" if record.cvu_cbu else user_name
            result.append((record.id, label))
        return result
