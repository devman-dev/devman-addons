from odoo import _, fields, models


class PfGatewayIncomingTransferCommissionAccountSyncWizard(models.TransientModel):
    _name = "pf.gateway.incoming.transfer.commission.account.sync.wizard"
    _description = "Asistente de sincronización de comisiones por usuario"

    cvu_cbu = fields.Char(string="CVU/CBU")
    limit = fields.Integer(default=200, required=True)
    offset = fields.Integer(default=0, required=True)

    def action_sync(self):
        self.ensure_one()
        model = self.env["pf.gateway.incoming.transfer.commission.account"]
        processed = model.sync_from_gateway(
            cvu_cbu=(self.cvu_cbu or "").strip() or None,
            limit=self.limit,
            offset=self.offset,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comisiones por usuario sincronizadas"),
                "message": _("Se procesaron %s registros.") % processed,
                "type": "success",
                "sticky": False,
                "next": self.env["ir.actions.actions"]._for_xml_id(
                    "pagoflex_wallet_gateway.action_pf_gateway_incoming_transfer_commission_account"
                ),
            },
        }