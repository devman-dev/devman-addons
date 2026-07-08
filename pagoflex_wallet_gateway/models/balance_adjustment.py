import uuid
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PagoflexBalanceAdjustment(models.Model):
    _name = "pagoflex.balance.adjustment"
    _description = "Ajustes de Saldo Manuales"
    _inherit = ["pf.gateway.client.mixin"]
    _order = "id desc"

    name = fields.Char(string="Referencia", required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta Bancaria", required=True)
    cvu_cbu = fields.Char(string="CVU/CBU", related="account_id.cvu_cbu", store=True)
    amount = fields.Monetary(string="Monto", required=True, currency_field="currency_id")
    currency_id = fields.Many2one('res.currency', string="Moneda", related="account_id.currency_id", readonly=True)
    direction = fields.Selection([
        ('credit', 'Acreditar'),
        ('debit', 'Debitar')
    ], string="Dirección", required=True)
    reason_code = fields.Selection([
        ('operational_correction', 'Corrección Operativa'),
        ('dispute_resolution', 'Resolución de Disputa'),
        ('manual_deposit', 'Depósito Manual'),
        ('manual_withdrawal', 'Retiro Manual'),
        ('reward_or_promotion', 'Premio o Promoción'),
        ('chargeback', 'Contracargo')
    ], string="Motivo", required=True)
    description = fields.Text(string="Descripción", required=True)
    external_reference = fields.Char(string="Referencia Externa")
    idempotency_key = fields.Char(string="Clave de Idempotencia", copy=False, readonly=True)
    gateway_adjustment_id = fields.Char(string="ID Gateway", copy=False, readonly=True, index=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('synced', 'Sincronizado'),
        ('failed', 'Error')
    ], string="Estado", default='draft', required=True, copy=False, tracking=True)
    operator_id = fields.Many2one("res.users", string="Operador", default=lambda self: self.env.user, readonly=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('pagoflex.balance.adjustment') or _('New')
            if not vals.get('idempotency_key'):
                vals['idempotency_key'] = str(uuid.uuid4())
        return super().create(vals_list)

    def _find_existing_gateway_adjustment(self, item):
        self.ensure_one()
        gateway_id = str(item.get("id") or "").strip()
        idempotency_key = str(item.get("idempotency_key") or "").strip()
        external_reference = str(item.get("external_reference") or "").strip()

        if gateway_id:
            existing = self.search([("gateway_adjustment_id", "=", gateway_id)], limit=1)
            if existing:
                return existing

        if idempotency_key:
            existing = self.search([("idempotency_key", "=", idempotency_key)], limit=1)
            if existing:
                return existing

        if external_reference:
            existing = self.search([("external_reference", "=", external_reference)], limit=1)
            if existing:
                return existing

        return self.browse()

    def _apply_gateway_adjustment_response(self, response, *, gateway_adjustment_id=None):
        self.ensure_one()
        response_data = response if isinstance(response, dict) else {}
        confirmed_id = gateway_adjustment_id or str(response_data.get("id") or "").strip() or False
        update_values = {"state": "synced"}
        if confirmed_id:
            update_values["gateway_adjustment_id"] = confirmed_id
        self.write(update_values)
        return update_values

    def _sync_from_gateway_items(self, items):
        processed = 0
        for item in items:
            if not isinstance(item, dict):
                continue

            matching_record = self._find_existing_gateway_adjustment(item)
            gateway_id = str(item.get("id") or "").strip() or False

            if matching_record:
                update_values = {"state": "synced"}
                if gateway_id:
                    update_values["gateway_adjustment_id"] = gateway_id
                matching_record.write(update_values)
            else:
                cvu_cbu = item.get("cvu_cbu")
                account = self.env["pf.gateway.bank.account"].search([("cvu_cbu", "=", cvu_cbu)], limit=1) if cvu_cbu else self.env["pf.gateway.bank.account"].browse()
                self.create(
                    {
                        "gateway_adjustment_id": gateway_id,
                        "account_id": account.id if account else False,
                        "cvu_cbu": cvu_cbu,
                        "amount": float(item.get("amount", 0.0)),
                        "direction": str(item.get("direction", "")).lower(),
                        "reason_code": str(item.get("reason_code", "")).lower(),
                        "description": item.get("description"),
                        "external_reference": item.get("external_reference"),
                        "idempotency_key": item.get("idempotency_key"),
                        "state": "synced",
                    }
                )

            processed += 1

        return processed

    def action_confirm_and_send(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Solo se pueden enviar ajustes en estado Borrador."))
        
        if self.amount <= 0:
            raise UserError(_("El monto debe ser mayor a cero."))

        if not self.idempotency_key:
            self.idempotency_key = str(uuid.uuid4())

        operator = self.operator_id or self.env.user
        operator_identifier = (operator.login or operator.name or "odoo") if operator else "odoo"

        payload = {
            "cvu_cbu": self.cvu_cbu,
            "amount": self.amount,
            "direction": self.direction.upper(),
            "reason_code": self.reason_code.upper(),
            "description": self.description,
            "external_reference": self.external_reference or self.name,
            "idempotency_key": self.idempotency_key,
            "operator_id": operator_identifier,
            "metadata": {
                "source": "odoo",
                "requested_by": operator_identifier,
            },
        }

        endpoint_path = "/admin/gateway/balance-adjustments"
        endpoint_url = f"{self._gateway_base_url()}{endpoint_path}"
        _logger.info(
            "Balance adjustment request method=POST url=%s payload=%s",
            endpoint_url,
            self._payload_to_text(payload),
        )

        try:
            response = self._gateway_request_json(
                "POST", endpoint_path, payload=payload
            )
            _logger.info(
                "Balance adjustment response url=%s payload=%s",
                endpoint_url,
                self._payload_to_text(response),
            )
            
            # The API usually returns {"id": "...", ...} or similar structure
            if response and response.get("id"):
                self.gateway_adjustment_id = str(response.get("id"))

            self._apply_gateway_adjustment_response(response, gateway_adjustment_id=self.gateway_adjustment_id)

            try:
                self.account_id.action_refresh_balance_sync()
            except Exception:
                _logger.exception(
                    "No se pudo refrescar el saldo de la cuenta tras confirmar el ajuste account_id=%s adjustment=%s",
                    self.account_id.id,
                    self.id,
                )
            
        except Exception as e:
            _logger.exception(
                "Balance adjustment failed url=%s payload=%s",
                endpoint_url,
                self._payload_to_text(payload),
            )
            self.state = 'failed'
            raise UserError(_("Error al enviar el ajuste al Gateway: %s") % str(e))

    def action_check_status(self):
        for record in self:
            if not record.gateway_adjustment_id:
                raise UserError(_("No hay ID del Gateway para consultar."))
                
            try:
                path = f"/admin/gateway/balance-adjustments/{record.gateway_adjustment_id}"
                response = record._gateway_request_json("GET", path)

                status = str(response.get("status") or response.get("state") or "").strip().lower() if isinstance(response, dict) else ""
                if status in {"failed", "error", "rejected"}:
                    record.write({"state": "failed"})
                else:
                    record._apply_gateway_adjustment_response(response, gateway_adjustment_id=record.gateway_adjustment_id)
                    
            except Exception as e:
                raise UserError(_("Error al consultar el estado: %s") % str(e))

    def action_force_sync(self):
        self.ensure_one()
        if not self.env.user.has_group("pagoflex_wallet_gateway.group_pagoflex_wallet_gateway_admin"):
            raise UserError(_("Solo los administradores pueden forzar la sincronización manual."))

        response = self._gateway_request_json("GET", "/admin/gateway/balance-adjustments")
        items = response.get("items", []) if isinstance(response, dict) else response
        if not isinstance(items, list):
            raise UserError(_("La respuesta del gateway no contiene una lista válida de ajustes."))

        for item in items:
            matching_record = self._find_existing_gateway_adjustment(item)
            if matching_record and matching_record.id == self.id:
                gateway_id = str(item.get("id") or "").strip() or self.gateway_adjustment_id
                self._apply_gateway_adjustment_response(item, gateway_adjustment_id=gateway_id)
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Sincronización completada"),
                        "message": _("El ajuste quedó marcado como sincronizado."),
                        "type": "success",
                        "sticky": False,
                        "next": {"type": "ir.actions.client", "tag": "reload"},
                    },
                }

        raise UserError(_("No se encontró el ajuste en el middleware para sincronizarlo manualmente."))

    @api.model
    def cron_sync_adjustments(self):
        """ Sincroniza los ajustes que hayan ocurrido directamente en el Gateway """
        try:
            response = self._gateway_request_json("GET", "/admin/gateway/balance-adjustments")
            
            # Asumiendo que retorna algo como {"items": [...]} o una lista
            items = response.get("items", []) if isinstance(response, dict) else response
            if not isinstance(items, list):
                _logger.warning("Respuesta inesperada al sincronizar ajustes: %s", response)
                return 0

            return self._sync_from_gateway_items(items)
        except Exception as e:
            _logger.error("Error sincronizando ajustes de saldo: %s", str(e))
            return 0

    @api.model
    def sync_from_gateway(self, mode="cron", sync_mode="incremental", job=None):
        return self.cron_sync_adjustments()
