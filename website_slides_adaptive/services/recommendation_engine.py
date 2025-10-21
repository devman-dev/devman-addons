# -*- coding: utf-8 -*-
from odoo import models

class RecommendationEngine(models.AbstractModel):
    _name = 'slide.recommendation.engine'
    _description = 'Motor de Recomendaciones para eLearning'

    def get_recommendations(self, user_id, channel_id, limit=5):
        Slide = self.env['slide.slide']
        Historial = self.env['slide.historial.progreso']
        Ruta = self.env['slide.ruta.aprendizaje']

        # Obtener ruta activa del usuario para ese canal
        ruta = Ruta.search([
            ('user_id', '=', user_id),
            ('channel_id', '=', channel_id),
            ('activa', '=', True)
        ], limit=1)

        nivel_dificultad = ruta.nivel_dificultad if ruta else 'basico'

        # Obtener slides del canal con ese nivel de dificultad
        all_slides = Slide.search([
            ('channel_id', '=', channel_id),
            ('nivel_dificultad', '=', nivel_dificultad),
        ])

        # Obtener las que ya completó el usuario
        historial_completado = Historial.search([
            ('user_id', '=', user_id),
            ('channel_id', '=', channel_id),
            ('completado', '=', True),
        ])
        completadas_ids = historial_completado.mapped('slide_id').ids

        # Filtrar las no completadas
        slides_recomendadas = all_slides.filtered(lambda s: s.id not in completadas_ids)

        # Orden por secuencia y limitar
        recomendadas = slides_recomendadas.sorted(key=lambda s: s.sequence)[:limit]

        return [{'id': s.id, 'name': s.name} for s in recomendadas]
