# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_slides.controllers.main import WebsiteSlides

class AdaptiveUIController(WebsiteSlides):

    @http.route('/slides/adaptive/dashboard', type='http', auth='user', website=True)
    def adaptive_dashboard(self, **kwargs):
        """Dashboard principal del estudiante con información adaptativa"""
        user = request.env.user

        historial = request.env['slide.historial.progreso'].search([
            ('user_id', '=', user.id)
        ], order='fecha_acceso desc', limit=50)

        rutas = request.env['slide.ruta.aprendizaje'].search([
            ('user_id', '=', user.id),
            ('activa', '=', True)
        ])

        total_tiempo = sum(historial.mapped('tiempo_dedicado'))
        total_completadas = len(historial.filtered(lambda h: h.completado))
        promedio_puntuacion = (
            sum(historial.mapped('puntuacion')) / len(historial)
        ) if historial else 0

        return request.render('website_slides_adaptive.student_dashboard', {
            'user': user,
            'historial': historial,
            'rutas': rutas,
            'total_tiempo': total_tiempo,
            'total_completadas': total_completadas,
            'promedio_puntuacion': promedio_puntuacion,
        })

    @http.route('/slides/adaptive/teacher/dashboard', type='http', auth='user', website=True)
    def teacher_dashboard(self, **kwargs):
        """Dashboard para profesores con análisis de estudiantes"""
        user = request.env.user

        canales = request.env['slide.channel'].search([
            ('user_id', '=', user.id)
        ])

        if not canales:
            return request.redirect('/slides')

        estudiantes_data = []
        for canal in canales:
            miembros = canal.slide_partner_ids
            for miembro in miembros:
                user_ids = miembro.partner_id.user_ids
                if not user_ids:
                    continue

                historial = request.env['slide.historial.progreso'].search([
                    ('user_id', '=', user_ids[0].id),
                    ('channel_id', '=', canal.id)
                ])

                if historial:
                    estudiantes_data.append({
                        'nombre': miembro.partner_id.name,
                        'canal': canal.name,
                        'progreso': len(historial.filtered(lambda h: h.completado)),
                        'tiempo_total': sum(historial.mapped('tiempo_dedicado')),
                        'promedio': sum(historial.mapped('puntuacion')) / len(historial) if historial else 0
                    })

        return request.render('website_slides_adaptive.teacher_dashboard', {
            'user': user,
            'canales': canales,
            'estudiantes_data': estudiantes_data,
        })

    @http.route('/slides/adaptive/ruta/<int:ruta_id>', type='http', auth='user', website=True)
    def ver_ruta(self, ruta_id, **kwargs):
        """Ver detalles de una ruta de aprendizaje específica"""
        ruta = request.env['slide.ruta.aprendizaje'].browse(ruta_id)

        if not ruta.exists() or ruta.user_id != request.env.user:
            return request.redirect('/slides/adaptive/dashboard')

        return request.render('website_slides_adaptive.ruta_detalle', {
            'ruta': ruta,
        })
