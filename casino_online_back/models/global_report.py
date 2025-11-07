# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools import float_round


class CasinoGlobalReport(models.TransientModel):
    _name = 'casino.global.report'
    _description = 'Reporte Global de Casino'
    _rec_name = 'id'

    # Filtros
    date_from = fields.Date(string='Fecha Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Fecha Hasta', required=True, default=fields.Date.context_today)
    time_from = fields.Float(string='Hora Desde', default=0.0)
    time_to = fields.Float(string='Hora Hasta', default=23.99)
    
    filter_type = fields.Selection([
        ('user', 'Jugador'),
        ('agent', 'Agente'),
    ], string='Filtrar por', default='user')
    
    user_id = fields.Many2one('res.users', string='Jugador')
    agent_id = fields.Many2one('res.partner', string='Agente', domain=[('is_agent', '=', True)])
    
    # Líneas del reporte
    line_ids = fields.One2many('casino.global.report.line', 'report_id', string='Líneas de Reporte')
    
    # Totales
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

    @api.depends('line_ids.apostado', 'line_ids.ganado', 'line_ids.netwin', 'line_ids.rake')
    def _compute_totals(self):
        for report in self:
            report.total_apostado = sum(report.line_ids.mapped('apostado'))
            report.total_ganado = sum(report.line_ids.mapped('ganado'))
            report.total_netwin = sum(report.line_ids.mapped('netwin'))
            report.total_rake = sum(report.line_ids.mapped('rake'))
            report.total_cargas = sum(report.line_ids.filtered(lambda l: l.categoria == 'Cargas y Retiros').mapped('apostado'))
            report.total_retiros = sum(report.line_ids.filtered(lambda l: l.categoria == 'Cargas y Retiros').mapped('ganado'))

    def action_generate_report(self):
        """Genera el reporte basado en los filtros"""
        self.ensure_one()
        
        # Limpiar líneas anteriores
        self.line_ids.unlink()
        
        # Construir dominio de fechas
        datetime_from = fields.Datetime.to_datetime(self.date_from)
        datetime_to = fields.Datetime.to_datetime(self.date_to)
        
        # Ajustar por horas
        datetime_from = datetime_from.replace(hour=int(self.time_from), minute=int((self.time_from % 1) * 60))
        datetime_to = datetime_to.replace(hour=int(self.time_to), minute=int((self.time_to % 1) * 60))
        
        # Dominio base para sesiones
        session_domain = [
            ('start_datetime', '>=', datetime_from),
            ('start_datetime', '<=', datetime_to),
        ]
        
        # Filtrar por usuario o agente
        if self.filter_type == 'user' and self.user_id:
            session_domain.append(('user_id', '=', self.user_id.id))
        elif self.filter_type == 'agent' and self.agent_id:
            session_domain.append(('agent_id', '=', self.agent_id.id))
        
        # Obtener sesiones
        sessions = self.env['casino.game.session'].search(session_domain)
        
        # Agrupar por categoría
        category_data = {}
        
        for session in sessions:
            if session.game_id and session.game_id.public_categ_ids:
                # Tomar la primera categoría pública del juego
                category_name = session.game_id.public_categ_ids[0].name
            else:
                category_name = 'Sin Categoría'
            
            if category_name not in category_data:
                category_data[category_name] = {
                    'apostado': 0.0,
                    'ganado': 0.0,
                    'netwin': 0.0,
                    'rake': 0.0,
                }
            
            # Calcular valores
            apostado = session.amount or 0.0
            ganado = 0.0
            
            if session.result == 'win':
                ganado = apostado + (session.net_loss or 0.0)  # Si ganó, recupera apuesta + ganancia
            elif session.result == 'loss':
                ganado = 0.0  # Si perdió, no gana nada
            elif session.result == 'draw':
                ganado = apostado  # Si empató, recupera la apuesta
            
            netwin = ganado - apostado
            rake = session.agent_commission or 0.0
            
            category_data[category_name]['apostado'] += apostado
            category_data[category_name]['ganado'] += ganado
            category_data[category_name]['netwin'] += netwin
            category_data[category_name]['rake'] += rake
        
        # Agregar Cargas y Retiros
        withdrawal_domain = [
            ('date', '>=', datetime_from),
            ('date', '<=', datetime_to),
        ]
        
        if self.filter_type == 'user' and self.user_id:
            withdrawal_domain.append(('partner_id', '=', self.user_id.partner_id.id))
        elif self.filter_type == 'agent' and self.agent_id:
            # Para agente, buscar todos los jugadores del agente
            user_ids = self.env['res.users'].search([('partner_id.agent_id', '=', self.agent_id.id)])
            if user_ids:
                partner_ids = user_ids.mapped('partner_id').ids
                withdrawal_domain.append(('partner_id', 'in', partner_ids))
        
        withdrawals = self.env['casino.game.withdrawals'].search(withdrawal_domain)
        
        total_cargas = sum(withdrawals.filtered(lambda w: w.amount > 0).mapped('amount'))
        total_retiros = abs(sum(withdrawals.filtered(lambda w: w.amount < 0).mapped('amount')))
        
        if total_cargas > 0 or total_retiros > 0:
            category_data['Cargas y Retiros'] = {
                'apostado': total_cargas,
                'ganado': total_retiros,
                'netwin': total_cargas - total_retiros,
                'rake': 0.0,
            }
        
        # Crear líneas del reporte
        line_vals = []
        for categoria, datos in category_data.items():
            line_vals.append((0, 0, {
                'report_id': self.id,
                'categoria': categoria,
                'apostado': datos['apostado'],
                'ganado': datos['ganado'],
                'netwin': datos['netwin'],
                'rake': datos['rake'],
            }))
        
        self.write({'line_ids': line_vals})
        
        # Retornar vista del reporte
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte Global',
            'res_model': 'casino.global.report',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': {'show_report': True},
        }


class CasinoGlobalReportLine(models.TransientModel):
    _name = 'casino.global.report.line'
    _description = 'Línea de Reporte Global'

    report_id = fields.Many2one('casino.global.report', string='Reporte', required=True, ondelete='cascade')
    categoria = fields.Char(string='Categoría', required=True)
    apostado = fields.Monetary(string='Apostado', currency_field='currency_id')
    ganado = fields.Monetary(string='Ganado', currency_field='currency_id')
    netwin = fields.Monetary(string='Netwin', currency_field='currency_id')
    rake = fields.Monetary(string='Rake', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='report_id.currency_id', store=True)
