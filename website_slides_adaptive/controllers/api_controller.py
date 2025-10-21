# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class APIController(http.Controller):

    @http.route('/api/slides/recommendations', type='json', auth='user', methods=['POST'])
    def get_recommendations(self, channel_id=None, limit=5):
        """Obtiene recomendaciones personalizadas para el usuario"""
        try:
            user = request.env.user
            recommendation_engine = request.env['slide.recommendation.engine']

            recommendations = recommendation_engine.get_recommendations(
                user.id,
                channel_id,
                limit=limit
            )

            return {
                'status': 'success',
                'data': recommendations
            }
        except Exception as e:
            _logger.error(f"Error al obtener recomendaciones: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
