# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools import float_round


class CasinoGlobalReportWizard(models.TransientModel):
    """Wizard para configurar filtros y generar el Reporte Global"""
    _name = 'casino.global.report.wizard'
    _description = 'Wizard de Filtros para Reporte Global'

    # Filtros
    date_from = fields.Date(string='Fecha Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Fecha Hasta', required=True, default=fields.Date.context_today)
    time_from = fields.Float(string='Hora Desde', default=0.0)
    time_to = fields.Float(string='Hora Hasta', default=23.99)
    
    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Jugador',
        domain=[('is_player', '=', True)]
    )
    
    def action_generate_report(self):
        """Genera y muestra el reporte con los filtros aplicados"""
        self.ensure_one()
        
        # Crear el reporte con los filtros
        report = self.env['casino.global.report'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'time_from': self.time_from,
            'time_to': self.time_to,
            'provider_id': self.provider_id.id if self.provider_id else False,
            'user_id': self.user_id.id if self.user_id else False,
        })
        
        # Generar los datos del reporte
        report._generate_report_data()
        
        # Mostrar el reporte en modo readonly
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte General',
            'res_model': 'casino.global.report',
            'res_id': report.id,
            'view_mode': 'form',
            'view_id': self.env.ref('casino_online_back.view_casino_global_report_result_form').id,
            'target': 'current',
        }


class CasinoGlobalReport(models.TransientModel):
    _name = 'casino.global.report'
    _description = 'Reporte Global de Casino'
    _rec_name = 'id'

    # Filtros (readonly en la vista de resultado)
    date_from = fields.Date(string='Fecha Desde', required=True, readonly=True)
    date_to = fields.Date(string='Fecha Hasta', required=True, readonly=True)
    time_from = fields.Float(string='Hora Desde', readonly=True)
    time_to = fields.Float(string='Hora Hasta', readonly=True)
    
    # filter_type = fields.Selection([
    #     ('user', 'Jugador'),
    #     ('agent', 'Agente'),
    # ], string='Filtrar por', readonly=True)
    
    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Jugador',
        domain=[('is_player', '=', True)]
    )

    # Líneas del reporte (almacenadas temporalmente)
    line_ids = fields.One2many('casino.global.report.line', 'report_id', string='Líneas de Reporte')
    
    # Totales (computados dinámicamente)
    total_apostado = fields.Monetary(string='Total Apostado', compute='_compute_totals', store=False)
    total_ganado = fields.Monetary(string='Total Ganado', compute='_compute_totals', store=False)
    total_netwin = fields.Monetary(string='Total Netwin', compute='_compute_totals', store=False)
    total_rake = fields.Monetary(string='Total Rake', compute='_compute_totals', store=False)
    total_cargas = fields.Monetary(string='Total Cargas', compute='_compute_totals', store=False)
    total_retiros = fields.Monetary(string='Total Retiros', compute='_compute_totals', store=False)
    
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)

    def name_get(self):
        """Mostrar siempre 'Reporte General' en lugar del ID"""
        return [(record.id, 'Reporte General') for record in self]

    def _generate_report_data(self):
        """Genera las líneas del reporte basándose en los filtros"""
        # Limpiar líneas anteriores
        self.line_ids = [(5, 0, 0)]
        
        # Construir dominio de fechas
        datetime_from = fields.Datetime.to_datetime(self.date_from)
        datetime_to = fields.Datetime.to_datetime(self.date_to)
        
        provider = self.provider_id

        user = self.user_id

        # Ajustar por horas
        datetime_from = datetime_from.replace(hour=int(self.time_from), minute=int((self.time_from % 1) * 60))
        datetime_to = datetime_to.replace(hour=int(self.time_to), minute=int((self.time_to % 1) * 60))
        
        # Dominio base para sesiones
        session_domain = [
            ('start_datetime', '>=', datetime_from),
            ('start_datetime', '<=', datetime_to)
        ]
        
        if provider:
            session_domain.append(('provider_id', '=', provider.id))

        if user:
            session_domain.append(('user_id', '=', user.id))
        
        # Obtener todas las categorías públicas existentes
        all_categories = self.env['product.public.category'].search([])
        
        # Inicializar category_data con todas las categorías en 0
        category_data = {}
        for category in all_categories:
            category_data[category.name] = {
                'apostado': 0.0,
                'ganado': 0.0,
                'netwin': 0.0,
                'rake': 0.0,
            }
        
        # Obtener sesiones
        sessions = self.env['casino.game.session'].search(session_domain)
        
        # Procesar sesiones y acumular datos
        for session in sessions:
            if session.game_id and session.game_id.public_categ_ids:
                category_name = session.game_id.public_categ_ids[0].name
            else:
                category_name = 'Sin Categoría'
                # Si no existe en el diccionario, agregarla
                if category_name not in category_data:
                    category_data[category_name] = {
                        'apostado': 0.0,
                        'ganado': 0.0,
                        'netwin': 0.0,
                        'rake': 0.0,
                    }
            
            # Calcular valores
            apostado = 0.0 #session.amount or 0.0
            ganado = 0.0
            
            if session.result in ['win', 'cancelled']:
                ganado += (session.amount or 0.0)
            else:
                apostado += (session.amount or 0.0)
            
            netwin = ganado - apostado
            rake = session.agent_commission or 0.0
            
            category_data[category_name]['apostado'] += apostado
            category_data[category_name]['ganado'] += ganado
            category_data[category_name]['netwin'] += netwin
            category_data[category_name]['rake'] += rake
        
        # Crear líneas del reporte para todas las categorías (incluso las que están en 0)
        line_vals = []
        for categoria, datos in sorted(category_data.items()):
            line_vals.append((0, 0, {
                'categoria': categoria,
                'apostado': datos['apostado'],
                'ganado': datos['ganado'],
                'netwin': datos['netwin'],
                'rake': datos['rake'],
            }))
        
        # Agregar línea de Cargas y Retiros al final
        # Calcular el total de Cargas y Retiros en el mismo período
        dt_from = datetime_from
        dt_to = datetime_to
        
        withdrawal_domain = [
            ('date', '>=', dt_from),
            ('date', '<=', dt_to),
            ('state', '=', 'approved')
        ]
        # if self.provider_id:
        #     withdrawal_domain.append(('provider_id', '=', self.provider_id.id))
        
        if self.user_id:
            withdrawal_domain.append(('partner_id', '=', self.user_id.id))

        withdrawals = self.env['casino.game.withdrawals'].search(withdrawal_domain)
        
        # Calcular total (cargas son positivas, retiros son negativos)
        # Cargas: operation_type == 'load'
        total_cargas = sum(withdrawals.filtered(lambda w: w.operation_type == 'load').mapped('amount'))
        # Retiros: sin operation_type o operation_type == 'withdrawal'
        total_retiros = sum(withdrawals.filtered(lambda w: not w.operation_type or w.operation_type == 'withdrawal').mapped('amount'))
        
        # Total neto: cargas - retiros
        total_cargas_retiros = total_cargas - total_retiros
        
        # Agregar línea al final del listado
        line_vals.append((0, 0, {
            'categoria': 'Cargas y Retiros',
            'apostado': total_cargas_retiros,  # Total neto en columna Apostado
            'ganado': 0.0,
            'netwin': total_cargas_retiros,    # Netwin = total neto
            'rake': 0.0,
        }))
        
        self.line_ids = line_vals

    def action_back_to_wizard(self):
        """Volver al wizard de filtros"""
        # Crear un nuevo wizard con los mismos filtros
        wizard = self.env['casino.global.report.wizard'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'time_from': self.time_from,
            'time_to': self.time_to,
            # 'filter_type': self.filter_type,
            'provider_id': self.provider_id.id if self.provider_id else False,
            'user_id': self.user_id.id if self.user_id else False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte General - Filtros',
            'res_model': 'casino.global.report.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_datetime_range(self):
        """Helper: arma (dt_from, dt_to) combinando fecha y hora."""
        self.ensure_one()
        dt_from = fields.Datetime.to_datetime(self.date_from)
        dt_to = fields.Datetime.to_datetime(self.date_to)
        dt_from = dt_from.replace(hour=int(self.time_from or 0.0),
                                   minute=int(((self.time_from or 0.0) % 1) * 60))
        dt_to = dt_to.replace(hour=int(self.time_to or 0.0),
                               minute=int(((self.time_to or 0.0) % 1) * 60))
        return dt_from, dt_to

    def action_view_withdrawals(self):
        """Abrir Cargas y Retiros en el período filtrado (y jugador si aplica)."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_range()
        domain = [('date', '>=', dt_from), ('date', '<=', dt_to)]
        # if self.provider_id:
        #     domain.append(('provider_id', '=', self.provider_id.id))
        if self.user_id:
            domain.append(('partner_id', '=', self.user_id.id))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cargas y Retiros',
            'res_model': 'casino.game.withdrawals',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
            'context': {'search_default_group_by_user': 0},
        }

    def action_view_sessions(self):
        """Abrir Sesiones de Juego del período (y jugador si aplica)."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_range()
        domain = [('start_datetime', '>=', dt_from), ('start_datetime', '<=', dt_to)]
        if self.provider_id:
            domain.append(('provider_id', '=', self.provider_id.id))
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sesiones de Juego',
            'res_model': 'casino.game.session',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }

    @api.depends(
        'line_ids.apostado', 'line_ids.ganado', 'line_ids.netwin', 'line_ids.rake',
        'date_from', 'date_to', 'time_from', 'time_to', 'provider_id', 'user_id'
    )
    def _compute_totals(self):
        """Calcula los totales basándose en las líneas"""
        for report in self:
            report.total_apostado = sum(report.line_ids.mapped('apostado'))
            report.total_ganado = sum(report.line_ids.mapped('ganado'))
            report.total_netwin = sum(report.line_ids.mapped('netwin'))
            report.total_rake = sum(report.line_ids.mapped('rake'))

            # Calcular Cargas y Retiros como totales separados (no en el listado por categoría)
            # Construir el rango datetime a partir de fecha+hora
            dt_from = fields.Datetime.to_datetime(report.date_from)
            dt_to = fields.Datetime.to_datetime(report.date_to)
            dt_from = dt_from.replace(hour=int(report.time_from or 0.0),
                                       minute=int(((report.time_from or 0.0) % 1) * 60))
            dt_to = dt_to.replace(hour=int(report.time_to or 0.0),
                                   minute=int(((report.time_to or 0.0) % 1) * 60))

            withdrawal_domain = [
                ('date', '>=', dt_from),
                ('date', '<=', dt_to),
            ]
            # if report.provider_id:
            #     withdrawal_domain.append(('provider_id', '=', report.provider_id.id))
            if report.user_id:
                withdrawal_domain.append(('partner_id', '=', report.user_id.id))

            withdrawals = self.env['casino.game.withdrawals'].search(withdrawal_domain)
            # Cargas: registros con operation_type == 'load'
            total_cargas = sum(withdrawals.filtered(lambda w: w.operation_type == 'load').mapped('amount'))
            # Retiros: registros sin operation_type definido o con operation_type == 'withdrawal'
            total_retiros = sum(withdrawals.filtered(lambda w: not w.operation_type or w.operation_type == 'withdrawal').mapped('amount'))

            report.total_cargas = total_cargas or 0.0
            report.total_retiros = total_retiros or 0.0


class CasinoGlobalReportLine(models.TransientModel):
    _name = 'casino.global.report.line'
    _description = 'Línea de Reporte Global'

    report_id = fields.Many2one('casino.global.report', string='Reporte', ondelete='cascade')
    categoria = fields.Char(string='Categoría')
    apostado = fields.Monetary(string='Apostado', currency_field='currency_id')
    ganado = fields.Monetary(string='Ganado', currency_field='currency_id')
    netwin = fields.Monetary(string='Netwin', currency_field='currency_id')
    rake = fields.Monetary(string='Rake', currency_field='currency_id')
    participacion = fields.Float(string='Peso %', compute='_compute_participacion', digits=(16, 4))
    currency_id = fields.Many2one('res.currency', related='report_id.currency_id')
    color = fields.Integer(string='Color Index', compute='_compute_color', store=False)

    @api.depends('categoria')
    def _compute_color(self):
        """Asigna un índice de color (0-11) basado en un hash del nombre de categoría"""
        for line in self:
            if line.categoria:
                # Generar un índice de color consistente basado en el hash del nombre
                hash_value = hash(line.categoria)
                # Odoo soporta colores del 0 al 11
                line.color = 0 #abs(hash_value) % 12
            else:
                line.color = 0

    @api.depends('apostado', 'report_id.total_apostado')
    def _compute_participacion(self):
        """Participación de la categoría sobre el Total Apostado (0..1)."""
        for line in self:
            total = line.report_id.total_apostado or 0.0
            line.participacion = (line.apostado / total) if total else 0.0
