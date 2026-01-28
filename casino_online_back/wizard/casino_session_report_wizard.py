from datetime import datetime, timedelta

from odoo import models, fields, api

class CasinoSessionReportWizard(models.TransientModel):
    _name = 'casino.session.report.wizard'
    _description = 'Wizard para Reporte de Sesiones de Casino'

    # Filtros de fecha
    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.today()
    )
    
    # Filtros de entidad
    user_id = fields.Many2one(
        'res.users',
        string='Jugador',
        domain=[('is_player', '=', True)]
    )

    agent_id = fields.Many2one(
        'res.partner',
        string='Agente',
        domain=[('is_agent', '=', True)]
    )
    
    # Filtros: Categoría y Proveedor
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría de Juego',
        help='Filtrar por categoría de producto'
    )
    seller_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        help='Filtrar por proveedor del juego'
    )

    # Campos computados para el resumen
    total_rounds = fields.Integer(string='Total de Rondas', readonly=True)
    total_games_count = fields.Integer(string='Total Jugadas (Cantidad)', readonly=True)
    total_games_amount = fields.Float(string='Total Jugadas (Monto)', readonly=True)
    total_wins_count = fields.Integer(string='Total Ganadas (Cantidad)', readonly=True)
    total_wins_amount = fields.Float(string='Total Ganadas (Monto)', readonly=True)
    total_losses_count = fields.Integer(string='Total Perdidas (Cantidad)', readonly=True)
    total_losses_amount = fields.Float(string='Total Perdidas (Monto)', readonly=True)
    player_classification = fields.Char(string='Clasificación del Jugador', readonly=True)

    def action_generate_report(self):
        """Genera el reporte basado en los filtros"""
        self.ensure_one()
        domain = self._build_search_domain()

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

    def _build_search_domain(self):
        """Construye el dominio de búsqueda con todos los filtros"""
        domain = []
        
        if self.date_from:
            domain.append(('start_datetime', '>=', self.date_from))
        if self.date_to:
            domain.append(('start_datetime', '<=', self.date_to))
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.agent_id:
            domain.append(('agent_id', '=', self.agent_id.id))
        
        # Filtros de categoría
        if self.category_id:
            products = self.env['product.template'].search([
                ('public_categ_ids', 'in', [self.category_id.id])
            ]).mapped('product_variant_ids')
            product_ids = products.ids
            domain.append(('game_id', 'in', product_ids))

        # Filtros de proveedor
        if self.seller_id:
            products = self.env['product.product'].search([
                ('product_tmpl_id.seller_ids.partner_id', '=', self.seller_id.id)
            ])
            product_ids = products.ids
            domain.append(('game_id', 'in', product_ids))
        
        return domain

    def _calculate_statistics(self, sessions):
        """Calcula las estadísticas del reporte"""
        if not sessions:
            self.total_rounds = 0
            self.total_games_count = 0
            self.total_games_amount = 0.0
            self.total_wins_count = 0
            self.total_wins_amount = 0.0
            self.total_losses_count = 0
            self.total_losses_amount = 0.0
            self.player_classification = "Sin datos"
            return

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
        
        win_ratio = self.total_wins_count / self.total_games_count
        net_balance = self.total_wins_amount - self.total_losses_amount
        
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
        domain = self._build_search_domain()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sesiones Filtradas',
            'res_model': 'casino.game.session',
            'view_mode': 'list,form',
            'domain': domain,
            'context': self.env.context,
        }