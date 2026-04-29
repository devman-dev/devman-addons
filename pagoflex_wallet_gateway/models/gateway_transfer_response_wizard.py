from odoo import fields, models


class PfGatewayTransferResponseWizard(models.TransientModel):
    _name = "pf.gateway.transfer.response.wizard"
    _description = "Respuesta de consulta al gateway"

    title = fields.Char(readonly=True)
    response_text = fields.Text(readonly=True, string="Respuesta")
