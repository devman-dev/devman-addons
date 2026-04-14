import json

from odoo import _, http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import Response, request


class CasinoApiProviderConfigController(http.Controller):
    def _service(self):
        return request.env["casino.api.provider.config.service"].sudo()

    def _json_response(self, payload, status=200):
        return Response(json.dumps(payload), status=status, content_type="application/json")

    def _ensure_access(self):
        user = request.env.user
        if not user.has_group("casino_api_gateway.group_provider_config_manager") and not user.has_group("base.group_system"):
            raise AccessError(_("No tiene permisos para administrar configuraciones YAML."))

    def _parse_payload(self):
        return request.get_json_data() or {}

    @http.route('/casino_api/v1/provider-configs', type='http', auth='user', methods=['GET'], csrf=False)
    def list_provider_configs(self, **kwargs):
        self._ensure_access()
        records = request.env['casino.provider.config'].sudo().search([], order='provider_code')
        items = [self._service().serialize_record(record) for record in records]
        return self._json_response({'status': 'success', 'items': items})

    @http.route('/casino_api/v1/provider-configs/<string:provider_code>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_provider_config(self, provider_code, **kwargs):
        self._ensure_access()
        record = request.env['casino.provider.config'].sudo().search([('provider_code', '=', provider_code)], limit=1)
        if not record:
            return self._json_response({'status': 'error', 'message': 'provider config not found'}, 404)
        return self._json_response({'status': 'success', 'item': self._service().serialize_record(record)})

    @http.route('/casino_api/v1/provider-configs/upload', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_provider_config(self, **kwargs):
        self._ensure_access()
        payload = self._parse_payload()
        try:
            record = self._service().upload_yaml(
                provider_code=payload.get('provider_code', ''),
                file_name=payload.get('file_name', ''),
                yaml_content=payload.get('yaml_content', ''),
                replace=bool(payload.get('replace')),
            )
            return self._json_response({'status': 'success', 'item': self._service().serialize_record(record)}, 201)
        except ValidationError as exc:
            return self._json_response({'status': 'error', 'message': str(exc)}, 400)

    @http.route('/casino_api/v1/provider-configs/<string:provider_code>', type='http', auth='user', methods=['PUT'], csrf=False)
    def replace_provider_config(self, provider_code, **kwargs):
        self._ensure_access()
        payload = self._parse_payload()
        try:
            record = self._service().replace_yaml(provider_code, payload.get('yaml_content', ''))
            return self._json_response({'status': 'success', 'item': self._service().serialize_record(record)})
        except ValidationError as exc:
            return self._json_response({'status': 'error', 'message': str(exc)}, 400)

    @http.route('/casino_api/v1/provider-configs/sync', type='http', auth='user', methods=['POST'], csrf=False)
    def sync_provider_configs(self, **kwargs):
        self._ensure_access()
        try:
            result = self._service().sync_from_disk()
            return self._json_response({'status': 'success', 'result': result})
        except ValidationError as exc:
            return self._json_response({'status': 'error', 'message': str(exc)}, 400)
