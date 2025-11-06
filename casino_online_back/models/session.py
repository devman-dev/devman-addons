from odoo import models, fields, api

class CasinoGameSession(models.Model):
    _name = 'casino.game.session'
    _description = 'Sesión de juego del jugador'
    _order = "id desc"

    token = fields.Char(string='Token')
    game_id = fields.Many2one('product.product', string='Juego')
    endGame = fields.Boolean(string='Fin del Juego')
    round_id = fields.Text(string='Ronda')
    transaction_id = fields.Text(string='Transacción')
    amount = fields.Monetary(string='BET')
    token_live = fields.Boolean(string='Token Live')

    user_id = fields.Many2one('res.users', string='Jugador', required=True)
    agent_id = fields.Many2one('res.partner', string='Agente', domain=[('is_company', '=', False)])
    start_datetime = fields.Datetime(string='Inicio')
    end_datetime = fields.Datetime(string='Fin')
    initial_balance = fields.Monetary(string='Saldo Inicial')
    net_loss = fields.Monetary(string='Pérdida Neta', currency_field='currency_id')
    final_balance = fields.Monetary(string='Saldo Final')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    # Datos de agente y comisión por débito
    agent_id = fields.Many2one(
        'res.partner',
        string='Agente',
        help='Agente asociado al jugador en el momento de la operación.'
    )
    agent_commission = fields.Monetary(
        string='Comisión del agente',
        currency_field='currency_id',
        help='Importe de la comisión del agente calculada sobre el monto debitado (amount × % comisión del juego).'
    )
    result = fields.Selection([
        ('win', 'Ganó'),
        ('loss', 'Perdió'),
        ('draw', 'Empate'),
        ('abandoned', 'Abandonada'),
        ('balance', 'Balance'),
        ('started', 'Started')
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

    group_display_name = fields.Char(
        string="Agrupación Detallada",
        compute="_compute_group_display_name",
        store=True
    )

    @api.depends('transaction_id', 'game_id', 'user_id', 'start_datetime')
    def _compute_group_display_name(self):
        for rec in self:
            rec.group_display_name = f"{rec.transaction_id or 'N/A'} - {rec.game_id.name or 'N/A'} - {rec.user_id.name or 'N/A'} - {rec.start_datetime.strftime('%Y-%m-%d %H:%M') if rec.start_datetime else 'N/A'}"

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
            