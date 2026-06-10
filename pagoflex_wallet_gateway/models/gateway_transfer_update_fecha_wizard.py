from odoo import models, fields, api

class PfGatewayTransferUpdateFechaWizard(models.TransientModel):
    _name = 'pf.gateway.transfer.update.fecha.wizard'
    _description = 'Wizard para actualizar fecha de negocio en transferencias'

    fecha_negocio = fields.Date(
        string='Nueva Fecha de Negocio',
        required=True,
        default=fields.Date.context_today
    )

    def action_update_fecha(self):
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            transfers = self.env['pf.gateway.transfer'].browse(active_ids)
            transfers.write({
                'fecha_negocio': self.fecha_negocio
            })
        return {'type': 'ir.actions.act_window_close'}
