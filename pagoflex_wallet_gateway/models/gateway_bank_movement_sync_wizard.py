from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PfGatewayBankMovementSyncWizard(models.TransientModel):
    _name = "pf.gateway.bank.movement.sync.wizard"
    _description = "Asistente de consulta de movimientos bancarios"

    bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta billetera")
    cbu_cvu_alias = fields.Char(string="CBU/CVU/Alias")
    start_date = fields.Date(string="Fecha desde", required=True)
    end_date = fields.Date(string="Fecha hasta", required=True)
    page_size = fields.Integer(string="Tamaño página", default=100, required=True)
    page_offset = fields.Integer(string="Offset página", default=1, required=True)
    fetch_all_pages = fields.Boolean(string="Traer todas las páginas", default=True)
    auto_reconcile = fields.Boolean(string="Conciliar automáticamente", default=True)
    _BANK_MOVEMENT_QUERY_CBU_PARAM = "pagoflex_wallet_gateway.bank_movement_query_cbu"

    @api.model
    def _get_fixed_bank_movement_query_cbu(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param(self._BANK_MOVEMENT_QUERY_CBU_PARAM) or ""
        ).strip()

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        if "start_date" in fields_list and not values.get("start_date"):
            values["start_date"] = today.replace(day=1)
        if "end_date" in fields_list and not values.get("end_date"):
            values["end_date"] = today

        fixed_query_cbu = self._get_fixed_bank_movement_query_cbu()
        if fixed_query_cbu:
            if "cbu_cvu_alias" in fields_list:
                values["cbu_cvu_alias"] = fixed_query_cbu
            if "bank_account_id" in fields_list:
                values["bank_account_id"] = False
        return values

    def action_sync(self):
        self.ensure_one()
        if self.start_date > self.end_date:
            raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))
        if self.page_size <= 0:
            raise UserError(_("El tamaño de página debe ser mayor a cero."))
        if self.page_offset <= 0:
            raise UserError(_("El offset de página debe ser mayor a cero."))

        fixed_query_cbu = self._get_fixed_bank_movement_query_cbu()
        result = self.env["pf.gateway.bank.movement"].sync_from_gateway_account(
            bank_account=self.env["pf.gateway.bank.account"].browse() if fixed_query_cbu else self.bank_account_id,
            cbu_cvu_alias=self.cbu_cvu_alias,
            start_date=self.start_date,
            end_date=self.end_date,
            page_size=self.page_size,
            page_offset=self.page_offset,
            fetch_all_pages=self.fetch_all_pages,
        )
        movements = self.env["pf.gateway.bank.movement"].browse(result["record_ids"])
        if self.auto_reconcile and movements:
            movements.action_auto_reconcile()
        return {
            "type": "ir.actions.act_window",
            "name": _("Movimientos bancarios importados"),
            "res_model": "pf.gateway.bank.movement",
            "view_mode": "list,form",
            "domain": [("id", "in", result["record_ids"] or [0])],
            "target": "current",
        }
