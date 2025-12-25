from odoo import models, fields, api
import json

class CasinoGameSession(models.Model):
    _name = 'casino.game.session'
    _description = 'Sesión de juego del jugador'
    _order = "id desc"

    token = fields.Char(string='Token')
    game_id = fields.Many2one('product.product', string='Juego')
    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        related='game_id.product_tmpl_id.provider_id',
        store=True,
        readonly=True,
        help='Proveedor (publisher) asociado al juego de la sesión.'
    )
    endGame = fields.Boolean(string='Fin del Juego')
    round_id = fields.Text(string='Ronda')
    transaction_id = fields.Text(string='Transacción')
    amount = fields.Monetary(string='BET')
    token_live = fields.Boolean(string='Token Live')

    user_id = fields.Many2one('res.users', string='Jugador', required=True)
    agent_id = fields.Many2one('res.partner', string='Agente', domain=[('is_company', '=', False)],  help='Agente asociado al jugador.')
    start_datetime = fields.Datetime(string='Inicio')
    end_datetime = fields.Datetime(string='Fin')
    initial_balance = fields.Monetary(string='Saldo Inicial')
    net_loss = fields.Monetary(string='Pérdida Neta', currency_field='currency_id')
    final_balance = fields.Monetary(string='Saldo Final')
    to_win = fields.Monetary(string='A Ganar', currency_field='currency_id', help='Monto que el jugador puede ganar en esta sesión.')
    events = fields.Text(string='Eventos')
    events_html = fields.Html(string='Eventos (Tabla)', compute='_compute_events_html', sanitize=False)
    currency_id = fields.Many2one('res.currency', string='Moneda')
    agent_commission = fields.Monetary(
        string='Comisión del agente',
        currency_field='currency_id',
        help='Importe de la comisión del agente calculada sobre el monto debitado (amount × % comisión del juego).'
    )
    result = fields.Selection([
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('draw', 'Draw'),
        ('abandoned', 'Abandoned'),
        ('balance', 'Balance'),
        ('started', 'Started'),
        ('in_progress', 'Running')
    ], string='Resultado')
    
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('in_progress', 'En curso'),
        ('finished', 'Finalizada'),
        ('error', 'Error'),
        ('logged_in', 'Logged In')
    ], default='pending', string='Estado')
    description = fields.Text(string='Descripción')
    move_ids = fields.One2many('account.move', 'game_session_id', string='Movimientos')
    json_data = fields.Text(string='JSON Recibido')
    internal_transaction_id = fields.Text(string='Transacción Interna')

    # Sesiones con el mismo transaction_id
    related_session_ids = fields.Many2many(
        'casino.game.session',
        string='Sesiones relacionadas',
        compute='_compute_related_session_ids',
        store=False
    )

    def _compute_related_session_ids(self):
        for rec in self:
            if rec.transaction_id:
                rec.related_session_ids = self.env['casino.game.session'].search(
                    [('transaction_id', '=', rec.transaction_id)], order='id asc'
                )
            else:
                rec.related_session_ids = self.env['casino.game.session']

    group_display_name = fields.Char(
        string="Agrupación Detallada",
        compute="_compute_group_display_name",
        store=True
    )

    @api.depends('transaction_id', 'game_id', 'user_id', 'start_datetime')
    def _compute_group_display_name(self):
        for rec in self:
            rec.group_display_name = f"{rec.transaction_id or 'N/A'} - {rec.game_id.name or 'N/A'} - {rec.user_id.name or 'N/A'} - {rec.start_datetime.strftime('%Y-%m-%d %H:%M') if rec.start_datetime else 'N/A'}"

    @api.depends('events')
    def _compute_events_html(self):
        """Convierte el campo events (JSON) en una tabla HTML con 3 columnas"""
        for rec in self:
            if not rec.events:
                rec.events_html = '<div class="o_casino_events_wrapper"><p class="text-muted" style="padding: 20px; text-align: center;">No hay eventos registrados</p></div>'
                continue
            
            try:
                events_list = json.loads(rec.events)
                if not events_list or not isinstance(events_list, list):
                    rec.events_html = '<div class="o_casino_events_wrapper"><p class="text-muted" style="padding: 20px; text-align: center;">No hay eventos registrados</p></div>'
                    continue
                
                # Construir tabla HTML con diseño de 3 columnas
                html = '''
                <div class="o_casino_events_wrapper">
                <style>
                    .o_casino_events_table {
                        width: 100%;
                        margin: 10px 0;
                    }
                    .o_events_grid {
                        display: grid;
                        grid-template-columns: repeat(3, 1fr);
                        gap: 15px;
                        padding: 10px;
                    }
                    .o_event_card {
                        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                        border-radius: 8px;
                        padding: 15px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                        transition: transform 0.2s, box-shadow 0.2s;
                    }
                    .o_event_card:hover {
                        transform: translateY(-2px);
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    }
                    .o_event_header {
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 8px 12px;
                        border-radius: 6px 6px 0 0;
                        margin: -15px -15px 10px -15px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    .o_event_row {
                        display: flex;
                        justify-content: space-between;
                        padding: 4px 0;
                        border-bottom: 1px solid rgba(0,0,0,0.05);
                        font-size: 12px;
                    }
                    .o_event_row:last-child {
                        border-bottom: none;
                    }
                    .o_event_label {
                        font-weight: 600;
                        color: #666;
                        min-width: 80px;
                    }
                    .o_event_value {
                        color: #333;
                        text-align: right;
                        flex: 1;
                    }
                    .o_event_badge {
                        display: inline-block;
                        padding: 2px 8px;
                        border-radius: 12px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    .o_badge_live {
                        background: #e74c3c;
                        color: white;
                    }
                    .o_badge_prelive {
                        background: #3498db;
                        color: white;
                    }
                    .o_event_cuota {
                        background: linear-gradient(135deg, #ffd89b 0%, #19547b 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    @media (max-width: 1200px) {
                        .o_events_grid {
                            grid-template-columns: repeat(2, 1fr);
                        }
                    }
                    @media (max-width: 768px) {
                        .o_events_grid {
                            grid-template-columns: 1fr;
                        }
                    }
                </style>
                <div class="o_casino_events_table">
                    <div class="o_events_grid">
                '''
                
                for event in events_list:
                    deporte = event.get('deporte', 'N/A')
                    categoria = event.get('categoria', 'N/A')
                    liga = event.get('liga', 'N/A')
                    evento = event.get('evento', 'N/A')
                    fecha = event.get('fecha', 'N/A')
                    mercado = event.get('mercado', 'N/A')
                    seleccion = event.get('seleccion', 'N/A')
                    cuota = event.get('cuota', 0)
                    live = event.get('live', False)
                    marcador = event.get('marcador')
                    momento = event.get('momento')
                    
                    live_badge = f'<span class="o_event_badge o_badge_live">🔴 LIVE</span>' if live else f'<span class="o_event_badge o_badge_prelive">Pre-Live</span>'
                    
                    html += f'''
                        <div class="o_event_card">
                            <div class="o_event_header">
                                {deporte} - {categoria}
                            </div>
                            <div class="o_event_row">
                                <span class="o_event_label">Liga:</span>
                                <span class="o_event_value">{liga}</span>
                            </div>
                            <div class="o_event_row">
                                <span class="o_event_label">Evento:</span>
                                <span class="o_event_value"><strong>{evento}</strong></span>
                            </div>
                            <div class="o_event_row">
                                <span class="o_event_label">Fecha:</span>
                                <span class="o_event_value">{fecha}</span>
                            </div>
                            <div class="o_event_row">
                                <span class="o_event_label">Mercado:</span>
                                <span class="o_event_value">{mercado}</span>
                            </div>
                            <div class="o_event_row">
                                <span class="o_event_label">Selección:</span>
                                <span class="o_event_value">{seleccion}</span>
                            </div>
                            <div class="o_event_row">
                                <span class="o_event_label">Cuota:</span>
                                <span class="o_event_value o_event_cuota">{cuota}</span>
                            </div>
                            <div class="o_event_row">
                                <span class="o_event_label">Live:</span>
                                <span class="o_event_value">{live}</span>
                            </div>
                    '''
                    
                    if marcador:
                        html += f'''
                            <div class="o_event_row">
                                <span class="o_event_label">Marcador:</span>
                                <span class="o_event_value">{marcador}</span>
                            </div>
                        '''
                    
                    if momento:
                        html += f'''
                            <div class="o_event_row">
                                <span class="o_event_label">Momento:</span>
                                <span class="o_event_value">{momento}</span>
                            </div>
                        '''
                    
                    html += '</div>'
                
                html += '''
                    </div>
                </div>
                </div>
                '''
                
                rec.events_html = html
                
            except (json.JSONDecodeError, Exception) as e:
                rec.events_html = f'<div class="o_casino_events_wrapper"><p class="text-danger" style="padding: 20px; text-align: center;">Error al procesar eventos: {str(e)}</p></div>'

    def _get_deposit_journal(self):
        """Obtiene el diario configurado para depósitos en la compañía"""
        return self.env.company.casino_deposit_journal_id
    
    def _get_bet_transfer_journal(self):
        """Obtiene el diario configurado para transferencias de apuestas en la compañía"""
        return self.env.company.casino_bet_transfer_journal_id
    
    def _get_deposit_account(self):
        """Obtiene la cuenta configurada para depósitos o la cuenta por defecto del diario"""
        company = self.env.company
        if company.casino_deposit_account_id:
            return company.casino_deposit_account_id
        elif company.casino_deposit_journal_id:
            return company.casino_deposit_journal_id.default_account_id
        return False
    
    def _get_bet_account(self):
        """Obtiene la cuenta configurada para apuestas o la cuenta por defecto del diario"""
        company = self.env.company
        if company.casino_bet_account_id:
            return company.casino_bet_account_id
        elif company.casino_bet_transfer_journal_id:
            return company.casino_bet_transfer_journal_id.default_account_id
        return False

    def create_deposit_move(self, amount, description="Depósito de usuario"):
        """
        Crea un asiento contable para registrar un depósito del usuario
        Utiliza el diario y cuenta configurados en la compañía
        """
        self.ensure_one()
        journal = self._get_deposit_journal()
        account = self._get_deposit_account()
        
        if not journal:
            raise ValueError("No se ha configurado un diario para depósitos en la compañía")
        if not account:
            raise ValueError("No se ha configurado una cuenta para depósitos en la compañía")
        
        # Crear el asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Depósito - {self.transaction_id}",
            'game_session_id': self.id,
            'line_ids': [
                (0, 0, {
                    'name': description,
                    'account_id': account.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': description,
                    'account_id': self.user_id.partner_id.property_account_receivable_id.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        return move

    def create_bet_transfer_move(self, amount, description="Transferencia de apuesta"):
        """
        Crea un asiento contable para registrar una transferencia de apuesta/pérdida
        Utiliza el diario y cuenta configurados en la compañía
        """
        self.ensure_one()
        journal = self._get_bet_transfer_journal()
        account = self._get_bet_account()
        
        if not journal:
            raise ValueError("No se ha configurado un diario para transferencias de apuestas en la compañía")
        if not account:
            raise ValueError("No se ha configurado una cuenta para transferencias de apuestas en la compañía")
        
        # Crear el asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Apuesta - {self.transaction_id}",
            'game_session_id': self.id,
            'line_ids': [
                (0, 0, {
                    'name': description,
                    'account_id': self.user_id.partner_id.property_account_receivable_id.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': description,
                    'account_id': account.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        return move

    def _get_deposit_journal(self):
        """Obtiene el diario configurado para depósitos en la compañía"""
        return self.env.company.casino_deposit_journal_id
    
    def _get_bet_transfer_journal(self):
        """Obtiene el diario configurado para transferencias de apuestas en la compañía"""
        return self.env.company.casino_bet_transfer_journal_id
    
    def _get_deposit_account(self):
        """Obtiene la cuenta configurada para depósitos o la cuenta por defecto del diario"""
        company = self.env.company
        if company.casino_deposit_account_id:
            return company.casino_deposit_account_id
        elif company.casino_deposit_journal_id:
            return company.casino_deposit_journal_id.default_account_id
        return False
    
    def _get_bet_account(self):
        """Obtiene la cuenta configurada para apuestas o la cuenta por defecto del diario"""
        company = self.env.company
        if company.casino_bet_account_id:
            return company.casino_bet_account_id
        elif company.casino_bet_transfer_journal_id:
            return company.casino_bet_transfer_journal_id.default_account_id
        return False

    def create_deposit_move(self, amount, description="Depósito de usuario"):
        """
        Crea un asiento contable para registrar un depósito del usuario
        Utiliza el diario y cuenta configurados en la compañía
        """
        self.ensure_one()
        journal = self._get_deposit_journal()
        account = self._get_deposit_account()
        
        if not journal:
            raise ValueError("No se ha configurado un diario para depósitos en la compañía")
        if not account:
            raise ValueError("No se ha configurado una cuenta para depósitos en la compañía")
        
        # Crear el asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Depósito - {self.transaction_id}",
            'game_session_id': self.id,
            'line_ids': [
                (0, 0, {
                    'name': description,
                    'account_id': account.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': description,
                    'account_id': self.user_id.partner_id.property_account_receivable_id.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        return move

    def create_bet_transfer_move(self, amount, description="Transferencia de apuesta"):
        """
        Crea un asiento contable para registrar una transferencia de apuesta/pérdida
        Utiliza el diario y cuenta configurados en la compañía
        """
        self.ensure_one()
        journal = self._get_bet_transfer_journal()
        account = self._get_bet_account()
        
        if not journal:
            raise ValueError("No se ha configurado un diario para transferencias de apuestas en la compañía")
        if not account:
            raise ValueError("No se ha configurado una cuenta para transferencias de apuestas en la compañía")
        
        # Crear el asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Apuesta - {self.transaction_id}",
            'game_session_id': self.id,
            'line_ids': [
                (0, 0, {
                    'name': description,
                    'account_id': self.user_id.partner_id.property_account_receivable_id.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': description,
                    'account_id': account.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        return move

    def _get_deposit_journal(self):
        """Obtiene el diario configurado para depósitos en la compañía"""
        return self.env.company.casino_deposit_journal_id
    
    def _get_bet_transfer_journal(self):
        """Obtiene el diario configurado para transferencias de apuestas en la compañía"""
        return self.env.company.casino_bet_transfer_journal_id
    
    def _get_deposit_account(self):
        """Obtiene la cuenta configurada para depósitos o la cuenta por defecto del diario"""
        company = self.env.company
        if company.casino_deposit_account_id:
            return company.casino_deposit_account_id
        elif company.casino_deposit_journal_id:
            return company.casino_deposit_journal_id.default_account_id
        return False
    
    def _get_bet_account(self):
        """Obtiene la cuenta configurada para apuestas o la cuenta por defecto del diario"""
        company = self.env.company
        if company.casino_bet_account_id:
            return company.casino_bet_account_id
        elif company.casino_bet_transfer_journal_id:
            return company.casino_bet_transfer_journal_id.default_account_id
        return False

    def create_deposit_move(self, amount, description="Depósito de usuario"):
        """
        Crea un asiento contable para registrar un depósito del usuario
        Utiliza el diario y cuenta configurados en la compañía
        """
        self.ensure_one()
        journal = self._get_deposit_journal()
        account = self._get_deposit_account()
        
        if not journal:
            raise ValueError("No se ha configurado un diario para depósitos en la compañía")
        if not account:
            raise ValueError("No se ha configurado una cuenta para depósitos en la compañía")
        
        # Crear el asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Depósito - {self.transaction_id}",
            'game_session_id': self.id,
            'line_ids': [
                (0, 0, {
                    'name': description,
                    'account_id': account.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': description,
                    'account_id': self.user_id.partner_id.property_account_receivable_id.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        return move

    def create_bet_transfer_move(self, amount, description="Transferencia de apuesta"):
        """
        Crea un asiento contable para registrar una transferencia de apuesta/pérdida
        Utiliza el diario y cuenta configurados en la compañía
        """
        self.ensure_one()
        journal = self._get_bet_transfer_journal()
        account = self._get_bet_account()
        
        if not journal:
            raise ValueError("No se ha configurado un diario para transferencias de apuestas en la compañía")
        if not account:
            raise ValueError("No se ha configurado una cuenta para transferencias de apuestas en la compañía")
        
        # Crear el asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"Apuesta - {self.transaction_id}",
            'game_session_id': self.id,
            'line_ids': [
                (0, 0, {
                    'name': description,
                    'account_id': self.user_id.partner_id.property_account_receivable_id.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': description,
                    'account_id': account.id,
                    'partner_id': self.user_id.partner_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        
        move = self.env['account.move'].create(move_vals)
        return move
            