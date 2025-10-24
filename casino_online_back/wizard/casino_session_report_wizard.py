from datetime import datetime, timedelta

from odoo import models, fields, api

class CasinoSessionReportWizard(models.TransientModel):
    _name = 'casino.session.report.wizard'
    _description = 'Wizard para Reporte de Sesiones de Casino'

    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.today
    )
    user_id = fields.Many2one(
        'res.users',
        string='Jugador'
    )
    agent_id = fields.Many2one(
        'res.partner',
        string='Agente',
        domain=[('is_company', '=', False)]
    )

    # Campos computados para el resumen
    total_rounds = fields.Integer(string='Total de Rondas', readonly=True)
    total_games_count = fields.Integer(string='Total Jugadas (Cantidad)', readonly=True)
    total_games_amount = fields.Monetary(string='Total Jugadas (Monto)', readonly=True)
    total_wins_count = fields.Integer(string='Total Ganadas (Cantidad)', readonly=True)
    total_wins_amount = fields.Monetary(string='Total Ganadas (Monto)', readonly=True)
    total_losses_count = fields.Integer(string='Total Perdidas (Cantidad)', readonly=True)
    total_losses_amount = fields.Monetary(string='Total Perdidas (Monto)', readonly=True)
    player_classification = fields.Char(string='Clasificación del Jugador', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)

    def action_generate_report(self):
        """Genera el reporte basado en los filtros"""
        self.ensure_one()
        # Construir el dominio de búsqueda
        domain = []
        
        if self.date_from:
            domain.append(('start_datetime', '>=', self.date_from))
        if self.date_to:
            domain.append(('start_datetime', '<=', self.date_to))
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.agent_id:
            domain.append(('agent_id', '=', self.agent_id.id))

        # Buscar las sesiones
        sessions = self.env['casino.game.session'].search(domain)
        
        # Calcular estadísticas
        self._calculate_statistics(sessions)
        
        # Retornar la misma vista del wizard con los resultados
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte de Sesiones de Casino',
            'res_model': 'casino.session.report.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def _calculate_statistics(self, sessions):
        """Calcula las estadísticas del reporte"""
        # Contar rondas únicas
        round_ids = sessions.mapped('round_id')
        unique_rounds = set(round_ids) if round_ids else set()
        self.total_rounds = len(unique_rounds)

        # Total de jugadas
        self.total_games_count = len(sessions)
        self.total_games_amount = sum(sessions.mapped('amount'))

        # Sesiones ganadas
        win_sessions = sessions.filtered(lambda s: s.result == 'win')
        self.total_wins_count = len(win_sessions)
        self.total_wins_amount = sum(win_sessions.mapped('amount'))

        # Sesiones perdidas
        loss_sessions = sessions.filtered(lambda s: s.result == 'loss')
        self.total_losses_count = len(loss_sessions)
        self.total_losses_amount = sum(loss_sessions.mapped('amount'))

        # Clasificación del jugador
        self.player_classification = self._classify_player()

    def _classify_player(self):
        """Clasifica al jugador según su rendimiento"""
        if self.total_games_count == 0:
            return "Sin datos suficientes"
        
        # Calcular ratio de ganancias
        win_ratio = self.total_wins_count / self.total_games_count if self.total_games_count > 0 else 0
        
        # Calcular balance neto
        net_balance = self.total_wins_amount - self.total_losses_amount
        
        # Clasificación basada en win ratio y balance neto
        if win_ratio >= 0.7 and net_balance > 0:
            return "Muy Rentable"
        elif win_ratio >= 0.5 and net_balance >= 0:
            return "Rentable"
        elif win_ratio >= 0.4 and abs(net_balance) <= (self.total_games_amount * 0.1):
            return "Neutro"
        else:
            return "Inconveniente"

    def action_view_sessions(self):
        """Muestra las sesiones filtradas en una vista de lista"""
        self.ensure_one()
        # Construir el dominio de búsqueda
        domain = []
        
        if self.date_from:
            domain.append(('start_datetime', '>=', self.date_from))
        if self.date_to:
            domain.append(('start_datetime', '<=', self.date_to))
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.agent_id:
            domain.append(('agent_id', '=', self.agent_id.id))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sesiones Filtradas',
            'res_model': 'casino.game.session',
            'view_mode': 'list,form',
            'domain': domain,
            'context': self.env.context,
        }