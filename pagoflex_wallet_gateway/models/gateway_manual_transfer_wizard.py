# -*- coding: utf-8 -*-
import logging
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class GatewayManualTransferWizard(models.TransientModel):
    _name = "gateway.manual.transfer.wizard"
    _inherit = "pf.gateway.client.mixin"
    _description = "Asistente de Transferencia Manual Gateway"

    is_reversal = fields.Boolean(
        string="¿Es Reversión?",
        help="Marque esta opción si se trata de una reversión de una transferencia previa.",
        default=False
    )
    origin_cbu_cvu = fields.Char(string="CVU/CBU Origen", required=True)
    destination_cbu_cvu = fields.Char(string="CVU/CBU Destino", required=True)
    amount = fields.Monetary(string="Monto", required=True)
    currency_id = fields.Many2one(
        'res.currency', 
        string="Moneda", 
        default=lambda self: self.env.ref('base.ARS').id, 
        required=True
    )
    description = fields.Char(string="Descripción", required=True)
    concept = fields.Selection([
        ('ALQ', 'Alquileres'),
        ('CUO', 'Cuotas'),
        ('EXP', 'Expensas'),
        ('FAC', 'Facturas'),
        ('HAB', 'Haberes'),
        ('HON', 'Honorarios'),
        ('PRE', 'Préstamos'),
        ('SEG', 'Seguros'),
        ('VAR', 'Varios'),
    ], string="Concepto", required=True, default='VAR')
    reason = fields.Text(string="Motivo de la transferencia")
    reference_origin_id = fields.Char(string="ID Referencia Origen (origin_id)")
    
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("El monto debe ser mayor a 0."))

    def action_confirm_transfer(self):
        self.ensure_one()

        # Generar idempotency_key
        prefix = "reversal" if self.is_reversal else "transfer"
        unique_id = str(uuid.uuid4())
        
        if self.reference_origin_id:
            idempotency_key = f"{prefix}-{self.reference_origin_id}-{unique_id}"
        else:
            idempotency_key = f"{prefix}-{unique_id}"
            
        currency_code = self.currency_id.name
        # Mapeo a códigos numéricos en caso de que sea necesario (el curl usa "032" para ARS)
        currency_map = {'ARS': '032', 'USD': '840'}
        currency_id_str = currency_map.get(currency_code, currency_code)
        
        payload = {
            "originCbuCvu": self.origin_cbu_cvu,
            "destinationCbuCvu": self.destination_cbu_cvu,
            "amount": self.amount,
            "description": self.description,
            "concept": self.concept,
            "currencyId": currency_id_str,
            "reason": self.reason or "",
            "reference_origin_id": self.reference_origin_id or "",
            "idempotency_key": idempotency_key
        }

        response = self._gateway_request_json(
            "POST",
            "/admin/gateway/transfer-request/manual",
            payload=payload,
        )
        _logger.info("Transferencia manual exitosa: %s", self._payload_to_text(response))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Transferencia Exitosa'),
                'message': _('La transferencia se ha enviado correctamente.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
