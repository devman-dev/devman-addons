from odoo import models, fields, api

class GatewayGlobalSettings(models.Model):
    _name = 'gateway.global.settings'
    _inherit = ['pf.gateway.client.mixin']
    _description = 'Gateway Global Settings'

    psp_mode_enabled = fields.Boolean(string="PSP Mode Enabled", default=False)
    personIdType = fields.Char(string="Person ID Type")
    personId = fields.Char(string="Person ID")
    personName = fields.Char(string="Person Name")

    @api.model
    def get_settings(self):
        # Return the singleton record (id=1)
        record = self.sudo().search([], limit=1, order='id asc')
        if not record:
            record = self.sudo().create({})
        return record

    def action_sync_from_gateway(self):
        self.ensure_one()
        response = self._gateway_request_json("GET", "/admin/gateway/global-settings")
        if isinstance(response, dict):
            self.write({
                'psp_mode_enabled': response.get('psp_mode_enabled', False),
                'personIdType': response.get('personIdType', ''),
                'personId': response.get('personId', ''),
                'personName': response.get('personName', ''),
            })

    @api.model
    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        settings = self.get_settings()
        settings.action_sync_from_gateway()
        return 1

    def action_push_to_gateway(self):
        self.ensure_one()
        if not self.psp_mode_enabled:
            if not self.personIdType or not self.personId or not self.personName:
                from odoo.exceptions import UserError
                raise UserError("Faltan campos obligatorios: personIdType, personId y personName son requeridos cuando PSP Mode está deshabilitado.")

        payload = {
            'psp_mode_enabled': self.psp_mode_enabled,
            'personIdType': self.personIdType or "",
            'personId': self.personId or "",
            'personName': self.personName or "",
        }
        self._gateway_request_json("PUT", "/admin/gateway/global-settings", payload=payload)
