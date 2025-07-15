import os
import base64
from odoo import http
from odoo.http import request, Response
from odoo.tools import config
import logging
import datetime
import json

_logger = logging.getLogger(__name__)

class MaintenanceRequestAPI(http.Controller):
    TOKEN = 'Ar@%Zca$QhPExdwzrf9/QHikFSwgm9' #config['maintenance_api_token'] or os.environ.get('maintenance_api_token', 'Ar@%Zca$QhPExdwzrf9/QHikFSwgm9')
    
    def _check_auth(self):
        token = request.httprequest.headers.get('Authorization')
        if token != f'Bearer {self.TOKEN}':
            return False
        return True

    def _unauthorized(self, type='json'):
        if type == 'json':
            return {'error': 'Unauthorized'}, 401
        
        return Response(json.dumps({'error': 'Unauthorized'}), content_type='application/json', status=401)
    
    def _not_found(self, type='json'):
        if type == 'json':
            return {'error': 'Not Found'}, 404

        return Response(json.dumps({'error': 'Not Found'}), content_type='application/json', status=404)
    
    @http.route('/api/v1/maintenance/requests', auth='public', methods=['GET'], type='http', csrf=False)
    def list_requests(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized('http')

        domain = []
        company_id = request.httprequest.args.get('company_id')
        date_from = request.httprequest.args.get('date_from')
        date_to = request.httprequest.args.get('date_to')

        if company_id:
            try:
                company_id = int(company_id)
            except ValueError:
                return {'error': 'Invalid company_id format. Must be an integer.'}, 400
            domain.append(('company_id', '=', company_id))

        if date_from:
            try:
                datetime.datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                return {'error': 'Invalid date_from format. Use YYYY-MM-DD.'}, 400
            domain.append(('request_date', '>=', date_from))
        if date_to:
            try:
                datetime.datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                return {'error': 'Invalid date_to format. Use YYYY-MM-DD.'}, 400
            domain.append(('request_date', '<=', date_to))

        records = request.env['maintenance.request'].sudo().search(domain)
        result = [
            {
                'id': rec.id,
                'name': rec.name,
                'company_id': rec.company_id.id,
                'equipment_id': rec.equipment_id.id,
                'maintenance_team_id': rec.maintenance_team_id.id,
                'priority': rec.priority,
                'stage': rec.stage_id.name,
                'description': rec.description,
                'request_date': rec.request_date.isoformat() if rec.request_date else None,
            }
            for rec in records
        ]
        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')

    @http.route('/api/v1/maintenance/request', auth='public', methods=['POST'], type='json', csrf=False)
    def create_request(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized('json')

        data = kwargs #.get('params', {})
        required_fields = ['name', 'description']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return {'error': f'Missing fields: {", ".join(missing)}'}, 400
        
         # Validar que maintenance_team_id pertenezca a company_id
        company_id = data.get('company_id')
        team_id = data.get('maintenance_team_id')
        if company_id and team_id:
            team = request.env['maintenance.team'].sudo().browse(team_id)
            if not team.exists() or team.company_id.id != int(company_id):
                return {'error': 'maintenance_team_id does not belong to the specified company_id.'}, 400

        # Validar que equipment_id pertenezca a company_id
        equipment_id = data.get('equipment_id')
        if company_id and equipment_id:
            equipment = request.env['maintenance.equipment'].sudo().browse(equipment_id)
            if not equipment.exists() or equipment.company_id.id != int(company_id):
                return {'error': 'equipment_id does not belong to the specified company_id.'}, 400

        try:
            record = request.env['maintenance.request'].sudo().create(data)
            return {'id': record.id, 'message': 'Created successfully'}
        except Exception as e:
            _logger.error("Error creating maintenance request: %s", e)
            return {'error': 'Server error'}, 500

    @http.route('/api/v1/maintenance/request/<int:request_id>', auth='public', methods=['PUT'], type='json', csrf=False)
    def update_request(self, request_id, **kwargs):
        if not self._check_auth():
            return self._unauthorized('json')

        record = request.env['maintenance.request'].sudo().browse(request_id)
        if not record.exists():
            return self._not_found('json')
        
        try:
            record.write(kwargs)
            return {'id': record.id, 'message': 'Updated successfully'}
        except Exception as e:
            _logger.error("Error updating maintenance request: %s", e)
            return {'error': 'Server error'}, 500
   
    @http.route('/api/v1/maintenance/request/<int:request_id>', auth='public', methods=['DELETE'], type='http', csrf=False)
    def delete_request(self, request_id, **kwargs):
        if not self._check_auth():
            return self._unauthorized('http')

        record = request.env['maintenance.request'].sudo().browse(request_id)
        if not record.exists():
            return self._not_found('http')
        
        try:
            record.unlink()
            return Response(json.dumps({'message': 'Deleted successfully'}), content_type='application/json')
        except Exception as e:
            _logger.error("Error deleting maintenance request: %s", e)
            return Response(json.dumps({'error': 'Server error'}), content_type='application/json', status=500)

    @http.route('/api/v1/maintenance/companies', auth='public', methods=['GET'], type='http', csrf=False)
    def get_companies(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized('http')

        domain = []
        company_id = request.httprequest.args.get('id')
        if company_id:
            try:
                company_id = int(company_id)
            except ValueError:
                return {'error': 'Invalid id format. Must be an integer.'}, 400
            domain.append(('id', '=', company_id))

        companies = request.env['res.company'].sudo().search(domain)
        result = [
            {
                'id': company.id,
                'name': company.name
            }
            for company in companies
        ]
        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')
    
    @http.route('/api/v1/maintenance/stages', auth='public', methods=['GET'], type='http', csrf=False)
    def get_stages(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized('http')

        domain = []
        stage_id = request.httprequest.args.get('id')
        if stage_id:
            try:
                stage_id = int(stage_id)
            except ValueError:
                return {'error': 'Invalid id format. Must be an integer.'}, 400
            domain.append(('id', '=', stage_id))

        # Obtener parámetros de idioma
        lang_param = request.httprequest.args.get('lang')
        all_langs = request.httprequest.args.get('all_langs') == 'true'

        stages = request.env['maintenance.stage'].sudo().search(domain)
        
        result = []
        for stage in stages:
            stage_data = {'id': stage.id}
            
            if all_langs:
                # Mostrar los nombres en todos los idiomas activos
                names_by_lang = {}
                active_langs = request.env['res.lang'].sudo().search([('active', '=', True)])
                for lang in active_langs:
                    name = stage.with_context(lang=lang.code).name
                    names_by_lang[lang.code] = name
                stage_data['name'] = names_by_lang

            elif lang_param:
                # Mostrar nombre traducido a un idioma específico
                translated_name = stage.with_context(lang=lang_param).name
                stage_data['name'] = translated_name

            else:
                # Mostrar nombre en idioma actual del entorno (por defecto)
                stage_data['name'] = stage.name

            result.append(stage_data)

        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')

    @http.route('/api/v1/maintenance/teams', auth='public', methods=['GET'], type='http', csrf=False)
    def get_teams(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized('http')

        domain = []
        company_id = request.httprequest.args.get('company_id')
        if company_id:
            try:
                company_id = int(company_id)
            except ValueError:
                return {'error': 'Invalid company_id format. Must be an integer.'}, 400
            domain.append(('company_id', '=', company_id))


        teams = request.env['maintenance.team'].sudo().search(domain)
        result = [
            {
                'id': team.id,
                'name': team.name,
               'company_id': team.company_id.id
            }
            for team in teams
        ]
        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')

    @http.route('/api/v1/maintenance/equipment', auth='public', methods=['GET'], type='http', csrf=False)
    def get_equipment(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized('http')

        domain = []
        company_id = request.httprequest.args.get('company_id')
        if company_id:
            try:
                company_id = int(company_id)
            except ValueError:
                return {'error': 'Invalid company_id format. Must be an integer.'}, 400
            domain.append(('company_id', '=', company_id))

        equipment = request.env['maintenance.equipment'].sudo().search(domain)
        result = [
            {
                'id': eq.id,
                'name': eq.name,
                'company_id': eq.company_id.id
            }
            for eq in equipment
        ]
        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')
