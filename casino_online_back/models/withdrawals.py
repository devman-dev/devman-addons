from odoo import models, fields, api

class CasinoGameWithdrawals(models.Model):
    _name = 'casino.game.withdrawals'
    _description = 'Withdrawals'
    _order = "id desc"

    transaction_id = fields.Char(string='Transaction ID', required=True, default='/')
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    # Campo auxiliar (almacenado) para facilitar búsquedas por día (filtros como "Hoy")
    date_date = fields.Date(string='Fecha (Día)', compute='_compute_date_date', store=True, index=True)
    description = fields.Char(string='Descripción')
    amount = fields.Float(string='Monto', required=True)
    amount_signed = fields.Float(string='Monto con Signo', compute='_compute_amount_signed', store=False)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Estado', default='pending')
    approved_by_id = fields.Many2one(
        comodel_name='res.users',
        string="Resuelto por",
        readonly=True
    )
    approved_date = fields.Datetime(
        string="Fecha Resolución",
        readonly=True
    )

    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    bank_id = fields.Many2one("casino.game.bank", string="Cuenta Bancaria")
    
    operation_type = fields.Selection([
        ('load', 'Carga'),
        ('withdrawal', 'Retiro'),
    ], string='Tipo de Operación')
    
    create_uid = fields.Many2one('res.users', string='Creado por', readonly=True)
    
    def action_change_state(self):
        new_state = self.env.context.get('new_state')
        if not new_state:
            return

        vals = {'state': new_state}

        if new_state == 'approved' or new_state == 'rejected':
            vals.update({
                'approved_by_id': self.env.uid,
                'approved_date': fields.Datetime.now(),
            })
            self.write(vals)

    # --------------------
    # COMPUTES
    # --------------------
    @api.depends('date')
    def _compute_date_date(self):
        for rec in self:
            rec.date_date = rec.date and rec.date.date() or False

    @api.depends('amount', 'operation_type')
    def _compute_amount_signed(self):
        """Calcular el monto con signo según el tipo de operación"""
        for rec in self:
            if rec.operation_type == 'withdrawal':
                rec.amount_signed = -abs(rec.amount)
            else:
                rec.amount_signed = abs(rec.amount)

    # --------------------
    # OVERRIDES
    # --------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Generar automáticamente transaction_id si no se proporciona"""
        for vals in vals_list:
            # Generar transaction_id si no existe
            if not vals.get('transaction_id') or vals.get('transaction_id') == '/':
                # Obtener el nombre del creador
                user = self.env.user
                user_name = user.name.split()[0] if user.name else 'USER'
                
                # Obtener el nombre del partner si existe
                partner_name = ''
                if vals.get('partner_id'):
                    partner = self.env['res.partner'].browse(vals['partner_id'])
                    partner_name = partner.name.split()[0] if partner.name else ''
                
                # Obtener tipo de operación
                op_type = vals.get('operation_type', 'OP')
                if op_type == 'load':
                    op_prefix = 'CAR'  # Carga
                elif op_type == 'withdrawal':
                    op_prefix = 'RET'  # Retiro
                else:
                    op_prefix = 'OP'
                
                # Generar un número secuencial basado en timestamp
                import time
                timestamp = int(time.time() * 1000) % 1000000  # Últimos 6 dígitos
                
                # Formato: [TIPO]-[USUARIO]-[PARTNER]-[TIMESTAMP]
                if partner_name:
                    vals['transaction_id'] = f"{op_prefix}-{user_name}-{partner_name}-{timestamp}"
                else:
                    vals['transaction_id'] = f"{op_prefix}-{user_name}-{timestamp}"
            
            # Para reporte de fichas (load/withdrawal), el estado siempre es 'approved'
            if vals.get('operation_type') in ['load', 'withdrawal']:
                if 'state' not in vals:
                    vals['state'] = 'approved'
                    vals['approved_by_id'] = self.env.uid
                    vals['approved_date'] = fields.Datetime.now()
        
        return super(CasinoGameWithdrawals, self).create(vals_list)
