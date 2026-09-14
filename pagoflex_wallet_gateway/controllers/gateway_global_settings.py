import json
from odoo import http
from odoo.http import request, Response

class GatewayGlobalSettingsController(http.Controller):

    def _check_api_key(self):
        api_key = request.httprequest.headers.get("x-api-key")
        expected_key = request.env["ir.config_parameter"].sudo().get_param("pagoflex_wallet_gateway.api_key")
        if not expected_key or api_key != expected_key:
            return False
        return True

    @http.route('/admin/gateway/global-settings', type='http', auth='public', methods=['GET', 'PUT'], csrf=False, cors='*')
    def handle_global_settings(self, **kwargs):
        if not self._check_api_key():
            return Response(json.dumps({"error": "Unauthorized"}), status=401, mimetype='application/json')

        settings = request.env['gateway.global.settings'].sudo().get_settings()

        if request.httprequest.method == 'GET':
            data = {
                "id": settings.id,
                "psp_mode_enabled": settings.psp_mode_enabled,
                "personIdType": settings.personIdType or "",
                "personId": settings.personId or "",
                "personName": settings.personName or "",
                "created_at": settings.create_date.strftime("%Y-%m-%dT%H:%M:%S.000000Z") if settings.create_date else "",
                "updated_at": settings.write_date.strftime("%Y-%m-%dT%H:%M:%S.000000Z") if settings.write_date else ""
            }
            return Response(json.dumps(data), status=200, mimetype='application/json')

        elif request.httprequest.method == 'PUT':
            try:
                body = json.loads(request.httprequest.data.decode('utf-8'))
            except json.JSONDecodeError:
                return Response(json.dumps({"error": "Invalid JSON"}), status=400, mimetype='application/json')

            required_fields = ["psp_mode_enabled", "personIdType", "personId", "personName"]
            if any(field not in body for field in required_fields):
                return Response(json.dumps({"error": "Missing required fields"}), status=400, mimetype='application/json')

            # Update fields
            vals = {
                "psp_mode_enabled": body["psp_mode_enabled"],
                "personIdType": body["personIdType"],
                "personId": body["personId"],
                "personName": body["personName"]
            }
            settings.write(vals)

            # Re-fetch to get updated values including dates
            data = {
                "id": settings.id,
                "psp_mode_enabled": settings.psp_mode_enabled,
                "personIdType": settings.personIdType or "",
                "personId": settings.personId or "",
                "personName": settings.personName or "",
                "created_at": settings.create_date.strftime("%Y-%m-%dT%H:%M:%S.000000Z") if settings.create_date else "",
                "updated_at": settings.write_date.strftime("%Y-%m-%dT%H:%M:%S.000000Z") if settings.write_date else ""
            }
            return Response(json.dumps(data), status=200, mimetype='application/json')
