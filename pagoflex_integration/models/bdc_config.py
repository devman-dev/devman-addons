from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    bdc_base_url = fields.Char(string="BDC Base URL", help="Base URL for BDC Conecta API (e.g. https://...)", default="")
    bdc_auth_type = fields.Selection([
        ("none", "None"),
        ("bearer", "Bearer Token (JWT/OAuth-like)"),
    ], default="bearer", string="Authentication Type", required=True)

    bdc_token_url = fields.Char(
        string="Token URL",
        help="Token endpoint URL if different from Base URL. If blank, module will use Base URL.",
        default="",
    )
    bdc_client_id = fields.Char(string="Client ID", help="Provided by BDC Conecta for Sandbox/Prod.")
    bdc_client_secret = fields.Char(string="Client Secret", help="Provided by BDC Conecta. Stored as system parameter.")
    bdc_token_param_key = fields.Char(
        string="Token Storage Key",
        default="bdc_conecta.access_token",
        help="System parameter key used to store the current access token.",
    )
    bdc_token_expiry_param_key = fields.Char(
        string="Token Expiry Storage Key",
        default="bdc_conecta.access_token_expiry",
        help="System parameter key used to store token expiry as an ISO datetime.",
    )

    def _bdc_get_param(self, key, default=None, sudo=True):
        ICP = self.env["ir.config_parameter"].sudo() if sudo else self.env["ir.config_parameter"]
        return ICP.get_param(key, default)

    def _bdc_set_param(self, key, value, sudo=True):
        ICP = self.env["ir.config_parameter"].sudo() if sudo else self.env["ir.config_parameter"]
        ICP.set_param(key, value)

    def bdc_get_access_token(self):
        self.ensure_one()
        token = self._bdc_get_param(self.bdc_token_param_key, default="")
        return token or ""

    def bdc_set_access_token(self, token, expiry_dt=None):
        self.ensure_one()
        self._bdc_set_param(self.bdc_token_param_key, token or "")
        if expiry_dt:
            self._bdc_set_param(self.bdc_token_expiry_param_key, fields.Datetime.to_string(expiry_dt))
        else:
            self._bdc_set_param(self.bdc_token_expiry_param_key, "")

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bdc_base_url = fields.Char(related="company_id.bdc_base_url", readonly=False)
    bdc_auth_type = fields.Selection(related="company_id.bdc_auth_type", readonly=False)
    bdc_token_url = fields.Char(related="company_id.bdc_token_url", readonly=False)
    bdc_client_id = fields.Char(related="company_id.bdc_client_id", readonly=False)
    bdc_client_secret = fields.Char(string="BDC Client Secret", help="Will be stored as system parameter.")

    bdc_token_param_key = fields.Char(related="company_id.bdc_token_param_key", readonly=False)
    bdc_token_expiry_param_key = fields.Char(related="company_id.bdc_token_expiry_param_key", readonly=False)

    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company
        secret = company._bdc_get_param("bdc_conecta.client_secret", default="")
        res.update({"bdc_client_secret": secret})
        return res

    def set_values(self):
        super().set_values()
        company = self.env.company
        if self.bdc_client_secret is not None:
            company._bdc_set_param("bdc_conecta.client_secret", self.bdc_client_secret or "")
