import os
import base64
from odoo import http
from odoo.http import request, Response
from odoo.tools import config
import logging
import datetime
import json
import re
import html

_logger = logging.getLogger(__name__)


class MaintenanceRequestAPI(http.Controller):
    TOKEN = 'Ar@%Zca$QhPExdwzrf9/QHikFSwgm9'

    # -----------------------------
    # AUTH / RESPONSES
    # -----------------------------
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

    # -----------------------------
    # PARSEO (DELIMITADO) DE TIPO
    # -----------------------------
    def _extract_tipo_mant(self, text):
        """
        Extrae SOLO si viene explícitamente delimitado.
        Acepta formatos como:
          - "Tipo de mantenimiento: Correctivo"
          - "tipo: Preventivo"
          - "tipo mantenimiento = Correctivo"
        Devuelve solo el valor (ej: "Correctivo") o None.
        """
        if not text:
            return None

        patterns = [
            r'(?im)^\s*tipo(?:\s+de)?\s+mantenim(?:iento)?\s*[:=\-]\s*(.+?)\s*$',
            r'(?im)^\s*tipo\s*[:=\-]\s*(.+?)\s*$',
        ]

        for p in patterns:
            m = re.search(p, text)
            if m:
                value = (m.group(1) or '').strip()
                value = re.split(r'\s*[|,;]\s*', value, maxsplit=1)[0].strip()
                return value[:128] if value else None

        return None

    # -----------------------------
    # ENDPOINT: LIST REQUESTS
    # -----------------------------
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
                return Response(
                    json.dumps({'error': 'Invalid company_id format. Must be an integer.'}),
                    content_type='application/json',
                    status=400
                )
            domain.append(('company_id', '=', company_id))

        if date_from:
            try:
                datetime.datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                return Response(
                    json.dumps({'error': 'Invalid date_from format. Use YYYY-MM-DD.'}),
                    content_type='application/json',
                    status=400
                )
            domain.append(('request_date', '>=', date_from))

        if date_to:
            try:
                datetime.datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                return Response(
                    json.dumps({'error': 'Invalid date_to format. Use YYYY-MM-DD.'}),
                    content_type='application/json',
                    status=400
                )
            domain.append(('request_date', '<=', date_to))

        records = request.env['maintenance.request'].sudo().search(domain)

        # Procesar cada registro para extraer y actualizar tipo_mant (desde description)
        for rec in records:
            tipo_mant = self._extract_tipo_mant(rec.description)
            if tipo_mant and rec.tipo_mant != tipo_mant:
                rec.sudo().write({'tipo_mant': tipo_mant})

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
                'tipo_mant': rec.tipo_mant,
                'request_date': rec.request_date.isoformat() if rec.request_date else None,
                'number_seq': rec.number_seq,
            }
            for rec in records
        ]

        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')

    # -----------------------------
    # ENDPOINT: CREATE REQUEST
    # -----------------------------
    @http.route('/api/v1/maintenance/request', auth='public', methods=['POST'], type='json', csrf=False)
    def create_request(self, **kwargs):
        if not self._check_auth():
            return self._unauthorized('json')

        data = kwargs  # .get('params', {})
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

            # Extraer tipo_mant desde description al crear (si viene delimitado)
            tipo_mant = self._extract_tipo_mant(record.description)
            if tipo_mant and record.tipo_mant != tipo_mant:
                record.sudo().write({'tipo_mant': tipo_mant})

            return {'id': record.id, 'message': 'Created successfully'}
        except Exception as e:
            _logger.error("Error creating maintenance request: %s", e)
            return {'error': 'Server error'}, 500

    # -----------------------------
    # ENDPOINT: UPDATE REQUEST
    # -----------------------------
    @http.route('/api/v1/maintenance/request/<int:request_id>', auth='public', methods=['PUT'], type='json', csrf=False)
    def update_request(self, request_id, **kwargs):
        if not self._check_auth():
            return self._unauthorized('json')

        record = request.env['maintenance.request'].sudo().browse(request_id)
        if not record.exists():
            return self._not_found('json')

        try:
            record.write(kwargs)

            # Si actualizaron description, intentá extraer tipo_mant (delimitado)
            if 'description' in kwargs:
                tipo_mant = self._extract_tipo_mant(kwargs.get('description'))
                if tipo_mant and record.tipo_mant != tipo_mant:
                    record.sudo().write({'tipo_mant': tipo_mant})

            return {'id': record.id, 'message': 'Updated successfully'}
        except Exception as e:
            _logger.error("Error updating maintenance request: %s", e)
            return {'error': 'Server error'}, 500

    # -----------------------------
    # ENDPOINT: DELETE REQUEST
    # -----------------------------
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

    # -----------------------------
    # NEW ENDPOINT: ADD NOTE -> UPDATE tipo_mant
    # -----------------------------

    @http.route('/api/v1/maintenance/request/<int:request_id>/note', auth='public', methods=['POST'], type='json',
                csrf=False)
    def add_note_and_update_tipo_mant(self, request_id, **kwargs):
        if not self._check_auth():
            return self._unauthorized('json')

        note = (kwargs.get('note') or '').strip()
        if not note:
            return {'error': 'Missing field: note'}, 400

        rec = request.env['maintenance.request'].sudo().browse(request_id)
        if not rec.exists():
            return self._not_found('json')

        # 1) Extraer y guardar tipo de mantenimiento (campo)
        tipo_mant = self._extract_tipo_mant(note)
        if tipo_mant and rec.tipo_mant != tipo_mant:
            rec.sudo().write({'tipo_mant': tipo_mant})

        # 2) Guardar TODO el texto en Notas internas (description)

        lines = [l.strip() for l in note.splitlines() if l.strip()]
        note_pretty = " | ".join(lines)
        rec.sudo().write({'description': note_pretty})

        return {
            'id': rec.id,
            'message': 'Saved successfully',
            'tipo_mant_saved': bool(tipo_mant),
            'tipo_mant_value': tipo_mant,
            'notes_field': 'description'
        }
    # -----------------------------
    # ENDPOINT: COMPANIES
    # -----------------------------
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
        result = [{'id': company.id, 'name': company.name} for company in companies]
        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')

    # -----------------------------
    # ENDPOINT: STAGES
    # -----------------------------
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

        lang_param = request.httprequest.args.get('lang')
        all_langs = request.httprequest.args.get('all_langs') == 'true'

        stages = request.env['maintenance.stage'].sudo().search(domain)

        result = []
        for stage in stages:
            stage_data = {'id': stage.id}

            if all_langs:
                names_by_lang = {}
                active_langs = request.env['res.lang'].sudo().search([('active', '=', True)])
                for lang in active_langs:
                    names_by_lang[lang.code] = stage.with_context(lang=lang.code).name
                stage_data['name'] = names_by_lang
            elif lang_param:
                stage_data['name'] = stage.with_context(lang=lang_param).name
            else:
                stage_data['name'] = stage.name

            result.append(stage_data)

        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')

    # -----------------------------
    # ENDPOINT: TEAMS
    # -----------------------------
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
        result = [{'id': team.id, 'name': team.name, 'company_id': team.company_id.id} for team in teams]
        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')

    # -----------------------------
    # ENDPOINT: EQUIPMENT
    # -----------------------------
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
        result = [{'id': eq.id, 'name': eq.name, 'company_id': eq.company_id.id} for eq in equipment]
        return Response(json.dumps({'count': len(result), 'results': result}), content_type='application/json')