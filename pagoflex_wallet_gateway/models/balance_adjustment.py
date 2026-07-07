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

    def action_confirm_and_send(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Solo se pueden enviar ajustes en estado Borrador."))
        
        if self.amount <= 0:
            raise UserError(_("El monto debe ser mayor a cero."))

        if not self.idempotency_key:
            self.idempotency_key = str(uuid.uuid4())

        payload = {
            "cvu_cbu": self.cvu_cbu,
            "amount": self.amount,
            "direction": self.direction.upper(),
            "reason_code": self.reason_code.upper(),
            "description": self.description,
            "external_reference": self.external_reference or self.name,
            "idempotency_key": self.idempotency_key
        }

        try:
            response = self._gateway_request_json(
                "POST", "/admin/gateway/balance-adjustments", payload=payload
            )
            
            # The API usually returns {"id": "...", ...} or similar structure
            if response and response.get("id"):
                self.gateway_adjustment_id = str(response.get("id"))
                
            self.state = 'synced'
            
        except Exception as e:
            self.state = 'failed'
            raise UserError(_("Error al enviar el ajuste al Gateway: %s") % str(e))

    def action_check_status(self):
        for record in self:
            if not record.gateway_adjustment_id:
                raise UserError(_("No hay ID del Gateway para consultar."))
                
            try:
                path = f"/admin/gateway/balance-adjustments/{record.gateway_adjustment_id}"
                response = record._gateway_request_json("GET", path)
                
                # Update status based on response if needed
                # Assuming the API returns a status field
                status = response.get("status", "").lower()
                if status == "completed":
                    record.state = "synced"
                elif status == "failed":
                    record.state = "failed"
                    
            except Exception as e:
                raise UserError(_("Error al consultar el estado: %s") % str(e))

    @api.model
    def cron_sync_adjustments(self):
        """ Sincroniza los ajustes que hayan ocurrido directamente en el Gateway """
        try:
            response = self._gateway_request_json("GET", "/admin/gateway/balance-adjustments")
            
            # Asumiendo que retorna algo como {"items": [...]} o una lista
            items = response.get("items", []) if isinstance(response, dict) else response
            if not isinstance(items, list):
                _logger.warning("Respuesta inesperada al sincronizar ajustes: %s", response)
                return

            for item in items:
                gateway_id = str(item.get("id"))
                if not gateway_id:
                    continue
                    
                existing = self.search([('gateway_adjustment_id', '=', gateway_id)], limit=1)
                if not existing:
                    cvu = item.get("cvu_cbu")
                    account = self.env['pf.gateway.bank.account'].search([('cvu_cbu', '=', cvu)], limit=1)
                    
                    self.create({
                        'gateway_adjustment_id': gateway_id,
                        'account_id': account.id if account else False,
                        'cvu_cbu': cvu,
                        'amount': float(item.get("amount", 0.0)),
                        'direction': str(item.get("direction", "")).lower(),
                        'reason_code': str(item.get("reason_code", "")).lower(),
                        'description': item.get("description"),
                        'external_reference': item.get("external_reference"),
                        'idempotency_key': item.get("idempotency_key"),
                        'state': 'synced',
                    })
        except Exception as e:
            _logger.error("Error sincronizando ajustes de saldo: %s", str(e))
