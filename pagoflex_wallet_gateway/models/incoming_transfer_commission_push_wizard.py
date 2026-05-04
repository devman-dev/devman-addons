from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class PfGatewayIncomingTransferCommissionPushWizard(models.TransientModel):
    _name = "pf.gateway.incoming.transfer.commission.push.wizard"
    _description = "Confirmación para actualizar comisión por defecto"

    setting_id = fields.Many2one(
        "pf.gateway.incoming.transfer.commission.settings",
        string="Configuración",
        required=True,
        ondelete="cascade",
    )
    app_name = fields.Char(related="setting_id.app_name", readonly=True)
    default_percentage = fields.Float(related="setting_id.default_percentage", readonly=True, digits=(16, 2))
    new_default_percentage = fields.Float(string="Nuevo porcentaje por defecto", required=True, digits=(16, 2))
    propagate_to_accounts = fields.Boolean(
        string="Propagar comisión a cuentas bancarias de esta app",
        default=False,
        help="Si se activa, cada cuenta asociada a la app quedará con el menor valor entre su comisión actual y la comisión por defecto.",
    )

    def action_confirm(self):
        self.ensure_one()
        if float_compare(self.new_default_percentage, 0.0, precision_digits=2) < 0:
            raise ValidationError(_("El porcentaje por defecto no puede ser negativo."))

        self.setting_id.with_context(skip_gateway_push=True).write(
            {"default_percentage": self.new_default_percentage}
        )
        return self.setting_id.action_push_to_gateway(
            propagate_to_accounts=self.propagate_to_accounts,
        )

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
