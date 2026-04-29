from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PfGatewayIncomingTransferCommissionSettings(models.Model):
    _name = "pf.gateway.incoming.transfer.commission.settings"
    _description = "Configuracion de comision para transferencias entrantes"

    name = fields.Char(default="Comisión por defecto", required=True)
    gateway_setting_id = fields.Integer(readonly=True)
    default_percentage = fields.Float(string="Porcentaje por defecto", digits=(16, 4))
    settlement_bank_account_id = fields.Char(string="ID cuenta bancaria liquidación", readonly=True)
    settlement_cvu = fields.Char(string="CVU de liquidación")
    is_active = fields.Boolean(string="Activo", default=True)
    created_at = fields.Datetime(readonly=True)
    updated_at = fields.Datetime(readonly=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True)

    _inherit = "pf.gateway.client.mixin"

    @api.constrains("default_percentage")
    def _check_default_percentage_supports_company_rules(self):
        for record in self:
            if float_compare(record.default_percentage, 0.0, precision_digits=4) < 0:
                raise ValidationError(_("El porcentaje por defecto no puede ser negativo."))

            line_model = self.env["pf.gateway.company.commission.agent"]
            grouped = line_model.read_group(
                [("active", "=", True)],
                ["percentage:sum"],
                ["company_partner_id"],
            )
            for group in grouped:
                total = group.get("percentage") or 0.0
                if float_compare(total, record.default_percentage, precision_digits=4) > 0:
                    company = self.env["res.partner"].browse(group["company_partner_id"][0])
                    raise ValidationError(
                        _("La empresa %(company)s ya tiene %(total).4f%% asignado a comisionistas; no puede bajar el máximo a %(max).4f%%.")
                        % {
                            "company": company.display_name,
                            "total": total,
                            "max": record.default_percentage,
                        }
                    )

    def _apply_gateway_payload(self, payload):
        if not isinstance(payload, dict):
            raise UserError(_("La respuesta del gateway no tiene el formato esperado."))

        values = {
            "gateway_setting_id": payload.get("id") or 0,
            "default_percentage": float(payload.get("default_percentage") or 0.0),
            "settlement_bank_account_id": payload.get("settlement_bank_account_id") or False,
            "settlement_cvu": payload.get("settlement_cvu") or False,
            "is_active": bool(payload.get("is_active")),
            "created_at": self._coerce_datetime(payload.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(payload.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
        }
        self.write(values)

    def action_sync_from_gateway(self):
        self.ensure_one()
        payload = self._gateway_request_json(
            "GET", "/admin/gateway/incoming-transfer-commission/settings"
        )
        self._apply_gateway_payload(payload)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comisión sincronizada"),
                "message": _("La configuración de comisión se actualizó desde el gateway."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_push_to_gateway(self):
        self.ensure_one()
        payload = {
            "default_percentage": self.default_percentage,
            "settlement_cvu": self.settlement_cvu or "",
            "is_active": self.is_active,
        }
        response = self._gateway_request_json(
            "POST", "/admin/gateway/incoming-transfer-commission/settings", payload=payload
        )
        self._apply_gateway_payload(response)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comisión actualizada"),
                "message": _("La configuración de comisión se envió correctamente al gateway."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
