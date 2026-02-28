# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from collections import defaultdict


class ProjectGoalsPortalDashboard(CustomerPortal):

    @http.route([
        '/my/goals', '/my/goals/page/<int:page>',
        '/goals', '/goals/page/<int:page>'
    ], type='http', auth='public', website=True)
    def portal_my_goals(self, page=1, sortby=None, filterby=None, search=None, **kw):
        """
        Muestra todos los objetivos de proyectos en el portal con KPIs
        Accesible públicamente sin necesidad de login
        """
        # Verificar si el usuario está logueado
        if request.env.user._is_public():
            values = {}
        else:
            values = self._prepare_portal_layout_values()
            
        Milestone = request.env['project.milestone'].sudo()
        
        # Dominio base
        domain = []
        
        # Aplicar búsqueda
        if search:
            domain += ['|', ('name', 'ilike', search), ('project_id', 'ilike', search)]
        
        # Opciones de ordenamiento
        searchbar_sortings = {
            'date': {'label': 'Fecha Límite', 'order': 'deadline desc'},
            'name': {'label': 'Nombre', 'order': 'name'},
            'project': {'label': 'Proyecto', 'order': 'project_id'},
        }
        
        # Filtros por estado
        searchbar_filters = {
            'all': {'label': 'Todos', 'domain': []},
            'achieved': {'label': 'Alcanzados', 'domain': [('is_reached', '=', True)]},
            'in_progress': {'label': 'En Progreso', 'domain': [('is_reached', '=', False), ('deadline', '>=', request.env.cr.now())]},
            'pending': {'label': 'Pendientes', 'domain': [('is_reached', '=', False)]},
        }
        
        # Ordenamiento por defecto
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Filtro por defecto
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Contar objetivos
        goal_count = Milestone.search_count(domain)
        
        # Debug: log el conteo
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"=== GOALS DEBUG === Total milestones encontrados: {goal_count}, dominio: {domain}")
        
        # Paginación
        pager = request.website.pager(
            url="/goals",
            url_args={'sortby': sortby, 'filterby': filterby, 'search': search},
            total=goal_count,
            page=page,
            step=self._items_per_page
        )
        
        # Obtener objetivos
        goals = Milestone.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        
        # Preparar datos de progreso para cada objetivo
        goals_data = []
        for goal in goals:
            tasks = request.env['project.task'].sudo().search([('milestone_id', '=', goal.id)])
            completed_tasks = len(tasks.filtered(lambda t: t.stage_id.fold))
            total_tasks = len(tasks)
            progress = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
            
            goals_data.append({
                'goal': goal,
                'completed_tasks': completed_tasks,
                'total_tasks': total_tasks,
                'progress': progress,
            })
        
        _logger.info(f"=== GOALS DEBUG === Total goals_data creados: {len(goals_data)}")
        
        # Calcular KPIs - Objetivos por estado
        all_goals = Milestone.search([])
        kpis = defaultdict(int)
        kpis['total'] = len(all_goals)
        kpis['achieved'] = len(all_goals.filtered(lambda g: g.is_reached))
        kpis['pending'] = len(all_goals.filtered(lambda g: not g.is_reached))
        kpis['in_progress'] = kpis['pending']  # Los que no están alcanzados están en progreso
        
        # Calcular porcentajes
        kpi_percentages = {}
        if kpis['total'] > 0:
            kpi_percentages['achieved'] = round((kpis['achieved'] / kpis['total']) * 100, 1)
            kpi_percentages['pending'] = round((kpis['pending'] / kpis['total']) * 100, 1)
            kpi_percentages['in_progress'] = kpi_percentages['pending']
        else:
            kpi_percentages = {'achieved': 0, 'pending': 0, 'in_progress': 0}
        
        values.update({
            'goals_data': goals_data,
            'page_name': 'goals',
            'pager': pager,
            'default_url': '/goals',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'search': search,
            'kpis': dict(kpis),
            'kpi_percentages': kpi_percentages,
        })
        
        _logger.info(f"=== GOALS DEBUG === Valores a pasar a plantilla - goals_data: {len(goals_data)}, kpis: {kpis}")
        
        return request.render("project_goals_portal_dashboard.portal_my_goals", values)

    @http.route(['/my/goal/<int:goal_id>', '/goal/<int:goal_id>'], type='http', auth='public', website=True)
    def portal_my_goal_detail(self, goal_id, **kw):
        """
        Muestra el detalle de un objetivo específico
        Accesible públicamente sin necesidad de login
        """
        goal = request.env['project.milestone'].sudo().browse(goal_id)
        
        if not goal.exists():
            return request.redirect('/goals')
        
        # Obtener tareas asociadas al objetivo
        tasks = request.env['project.task'].sudo().search([('milestone_id', '=', goal_id)])
        
        # KPIs del objetivo
        task_kpis = {
            'total': len(tasks),
            'done': len(tasks.filtered(lambda t: t.stage_id.fold)),
            'in_progress': len(tasks.filtered(lambda t: not t.stage_id.fold)),
        }
        
        # Calcular progreso del objetivo
        if task_kpis['total'] > 0:
            progress_percentage = round((task_kpis['done'] / task_kpis['total']) * 100, 1)
        else:
            progress_percentage = 0
        
        values = {
            'goal': goal,
            'tasks': tasks,
            'task_kpis': task_kpis,
            'progress_percentage': progress_percentage,
            'page_name': 'goals',
        }
        
        return request.render("project_goals_portal_dashboard.portal_my_goal_detail", values)
