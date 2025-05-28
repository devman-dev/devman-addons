import os
import base64
from odoo import http
from odoo.http import request
from odoo.tools import config
import logging

_logger = logging.getLogger(__name__)

class MaintenanceRequestAPI(http.Controller):
    TOKEN = 'Ar@%Zca$QhPExdwzrf9/QHikFSwgm9' #config['maintenance_api_token'] or os.environ.get('maintenance_api_token', 'Ar@%Zca$QhPExdwzrf9/QHikFSwgm9')
    
    def _check_auth(self):
        token = request.httprequest.headers.get('Authorization')
        if token != f'Bearer {self.TOKEN}':
            return False
        return True

    def _unauthorized(self):
        return {'error': 'Unauthorized'}, 401

    def _not_found(self):
        return {'error': 'Not Found'}, 404
        
    @http.route('/api/maintenance/requests', auth='public', methods=['GET'], type='json', csrf=False)
    def list_requests(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized()

        records = request.env['maintenance.request'].sudo().search([])
        return [
            {
                'id': rec.id,
                'name': rec.name,
                'equipment_id': rec.equipment_id.id,
                'maintenance_team_id': rec.maintenance_team_id.id,
                'priority': rec.priority,
                'description': rec.description,
            }
            for rec in records
        ]

    @http.route('/api/maintenance/request', auth='public', methods=['POST'], type='json', csrf=False)
    def create_request(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized()

        data = kwargs #.get('params', {})
        required_fields = ['name', 'description']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return {'error': f'Missing fields: {", ".join(missing)}'}, 400
        
        try:
            record = request.env['maintenance.request'].sudo().create(data)
            return {'id': record.id, 'message': 'Created successfully'}
        except Exception as e:
            _logger.error("Error creating maintenance request: %s", e)
            return {'error': 'Server error'}, 500

    @http.route('/api/maintenance/request/<int:request_id>', auth='public', methods=['PUT'], type='json', csrf=False)
    def update_request(self, request_id, **kwargs):
        if not self._check_auth():
            return self._unauthorized()

        record = request.env['maintenance.request'].sudo().browse(request_id)
        if not record.exists():
            return self._not_found()
        
        try:
            record.write(kwargs)
            return {'id': record.id, 'message': 'Updated successfully'}
        except Exception as e:
            _logger.error("Error updating maintenance request: %s", e)
            return {'error': 'Server error'}, 500

    @http.route('/api/maintenance/request/<int:request_id>', auth='public', methods=['PATCH'], type='json', csrf=False)
    def partial_update_request(self, request_id, **kwargs):
        return self.update_request(request_id, **kwargs)
        
    @http.route('/api/maintenance/request/<int:request_id>', auth='public', methods=['DELETE'], type='json', csrf=False)
    def delete_request(self, request_id, **kwargs):
        if not self._check_auth():
            return self._unauthorized()

        record = request.env['maintenance.request'].sudo().browse(request_id)
        if not record.exists():
            return self._not_found()
        
        try:
            record.unlink()
            return {'message': 'Deleted successfully'}
        except Exception as e:
            _logger.error("Error deleting maintenance request: %s", e)
            return {'error': 'Server error'}, 500

    @http.route('/api/maintenance/teams', auth='public', methods=['GET'], type='json', csrf=False)
    def get_teams(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized()

        teams = request.env['maintenance.team'].sudo().search([])
        return [{'id': team.id, 'name': team.name} for team in teams]

    @http.route('/api/maintenance/equipment', auth='public', methods=['GET'], type='json', csrf=False)
    def get_equipment(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized()

        equipment = request.env['maintenance.equipment'].sudo().search([])
        return [{'id': eq.id, 'name': eq.name} for eq in equipment]
