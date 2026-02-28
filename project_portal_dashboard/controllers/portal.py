# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from collections import defaultdict


class ProjectPortalDashboard(CustomerPortal):

    @http.route([
        '/my/projects', '/my/projects/page/<int:page>',
        '/projects', '/projects/page/<int:page>'
    ], type='http', auth='public', website=True)
    def portal_my_projects(self, page=1, sortby=None, filterby=None, search=None, **kw):
        """
        Muestra todos los proyectos en el portal con KPIs
        Accesible públicamente sin necesidad de login
        """
        # Verificar si el usuario está logueado para preparar valores del portal
        if request.env.user._is_public():
            values = {}
        else:
            values = self._prepare_portal_layout_values()
            
        Project = request.env['project.project'].sudo()
        
        # Dominio base - todos los proyectos
        domain = []
        
        # Aplicar búsqueda
        if search:
            domain += ['|', ('name', 'ilike', search), ('partner_id', 'ilike', search)]
        
        # Opciones de ordenamiento
        searchbar_sortings = {
            'date': {'label': 'Fecha', 'order': 'create_date desc'},
            'name': {'label': 'Nombre', 'order': 'name'},
        }
        
        # Filtros por estado - usar sudo() para obtener stages
        searchbar_filters = {
            'all': {'label': 'Todos', 'domain': []},
        }
        
        # Obtener stages dinámicamente con sudo()
        stages = request.env['project.project.stage'].sudo().search([])
        for stage in stages:
            searchbar_filters[f'stage_{stage.id}'] = {
                'label': stage.name,
                'domain': [('stage_id', '=', stage.id)]
            }
        
        # Ordenamiento por defecto
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Filtro por defecto
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Contar proyectos con sudo()
        project_count = Project.search_count(domain)
        
        # Paginación
        pager = request.website.pager(
            url="/projects",
            url_args={'sortby': sortby, 'filterby': filterby, 'search': search},
            total=project_count,
            page=page,
            step=self._items_per_page
        )
        
        # Obtener proyectos con sudo() (ya está aplicado en Project)
        projects = Project.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        
        # Calcular KPIs - Proyectos por estado (usar sudo para evitar errores de permisos)
        all_projects = Project.search([])
        kpis = defaultdict(int)
        kpis['total'] = len(all_projects)
        
        for project in all_projects:
            if project.stage_id:
                kpis[project.stage_id.name] = kpis.get(project.stage_id.name, 0) + 1
            else:
                kpis['Sin Estado'] = kpis.get('Sin Estado', 0) + 1
        
        # Calcular porcentajes
        kpi_percentages = {}
        if kpis['total'] > 0:
            for key, value in kpis.items():
                if key != 'total':
                    kpi_percentages[key] = round((value / kpis['total']) * 100, 1)
        
        values.update({
            'projects': projects,
            'page_name': 'project',
            'pager': pager,
            'default_url': '/projects',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'search': search,
            'kpis': dict(kpis),
            'kpi_percentages': kpi_percentages,
            'stages': stages,
        })
        
        return request.render("project_portal_dashboard.portal_my_projects", values)

    @http.route(['/my/project/<int:project_id>', '/project/<int:project_id>'], type='http', auth='public', website=True)
    def portal_my_project_detail(self, project_id, **kw):
        """
        Muestra el detalle de un proyecto específico
        Accesible públicamente sin necesidad de login
        """
        project = request.env['project.project'].sudo().browse(project_id)
        
        if not project.exists():
            return request.redirect('/projects')
        
        # Obtener tareas del proyecto con sudo()
        tasks = request.env['project.task'].sudo().search([('project_id', '=', project_id)])
        
        # KPIs del proyecto
        task_kpis = {
            'total': len(tasks),
            'done': len(tasks.filtered(lambda t: t.stage_id.fold)),
            'in_progress': len(tasks.filtered(lambda t: not t.stage_id.fold)),
        }
        
        values = {
            'project': project,
            'tasks': tasks,
            'task_kpis': task_kpis,
            'page_name': 'project',
        }
        
        return request.render("project_portal_dashboard.portal_my_project_detail", values)
