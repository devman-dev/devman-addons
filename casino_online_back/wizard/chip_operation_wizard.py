from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class ChipOperationWizard(models.TransientModel):
    _name = 'chip.operation.wizard'
    _description = 'Wizard para Reporte de Fichas'

    partner_id = fields.Many2one(
        'res.partner', 
        string='Cliente / Proveedor', 
        required=True,
        help='Si el usuario es agente: sólo sus subagentes y jugadores directos. Si es administrador: todos.'
    )

    # Se utilizará para validación únicamente; no se mostrará en la vista.
    allowed_partner_ids = fields.Many2many(
        'res.partner',
        string='Partners Permitidos',
        compute='_compute_allowed_partner_ids'
    )
    
    amount = fields.Float(
        string='Importe', 
        required=True,
        digits=(16, 2)
    )
    
    operation_type = fields.Selection([
        ('load', 'Carga de Fichas'),
        ('withdrawal', 'Retiro de Fichas'),
    ], string='Tipo de Operación', required=True, default='load')
    
    description = fields.Text(
        string='Observaciones',
        help='Agregue comentarios o detalles adicionales sobre esta operación'
    )
    
    date = fields.Datetime(
        string='Fecha y Hora', 
        required=True, 
        default=fields.Datetime.now,
        readonly=True
    )

    # --------------------------------------------------
    # Acceso / Dominio dinámico
    # --------------------------------------------------
    def _is_admin_user(self):
        """Determinar si el usuario tiene privilegios de administrador de operaciones.
        Criterio: pertenecer al grupo base.group_system o manejar un grupo específico si existiera.
        """
        user = self.env.user
        return user.has_group('base.group_system')

    def _compute_allowed_partner_ids(self):
        """Construye la lista de partners seleccionables:
        - Admin: todos los partners que sean jugadores o agentes (flexible)
        - Agente: sus subagentes directos y jugadores directos
        NOTA: No baja recursivamente más de un nivel (requisito).
        """
        for wiz in self:
            Partner = self.env['res.partner']
            if wiz._is_admin_user():
                # Todos los agentes y jugadores
                allowed = Partner.search(['|', ('is_agent', '=', True), ('is_player', '=', True)])
            else:
                # Usuario agente: identificar su partner (asumimos user.partner_id es el agente)
                current_partner = wiz.env.user.partner_id
                domain_direct_children = ['|',
                    ('agent_id', '=', current_partner.id),       # jugadores directos
                    ('parent_agent_id', '=', current_partner.id) # subagentes directos
                ]
                allowed = Partner.search(domain_direct_children)
            wiz.allowed_partner_ids = allowed

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Inyecta el dominio del campo partner_id en la vista FORM de forma dinámica según el usuario.
        Evita errores de evaluación en el cliente usando IDs directos y no expresiones Python.
        """
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            self._compute_allowed_partner_ids()
            if not self._is_admin_user():
                from lxml import etree
                arch = etree.XML(res['arch'])
                field_nodes = arch.xpath("//field[@name='partner_id']")
                if field_nodes:
                    ids = self.allowed_partner_ids.ids
                    # Dominio con los IDs explícitos
                    field_nodes[0].set('domain', "[('id','in', %s)]" % ids)
                res['arch'] = etree.tostring(arch, encoding='unicode')
        return res

    @api.constrains('amount')
    def _check_amount(self):
        """Validar que el importe sea positivo"""
        for record in self:
            if record.amount <= 0:
                raise ValidationError('El importe debe ser mayor a cero.')

    def action_confirm(self):
        """Confirmar y crear la operación usando el flujo central de money.flow"""
        self.ensure_one()
        
        # Validar datos antes de crear
        if not self.partner_id:
            raise UserError('Debe seleccionar un jugador o agente.')

        # Validación de seguridad: el partner elegido debe estar permitido para el usuario agente
        if not self._is_admin_user():
            if self.partner_id not in self.allowed_partner_ids:
                raise ValidationError('No tiene permiso para operar con este partner (no es de su nivel inmediato).')
        
        if self.amount <= 0:
            raise UserError('El importe debe ser mayor a cero.')
        
        # Preparar descripción
        operation_name = dict(self._fields['operation_type'].selection).get(self.operation_type)
        description = self.description or f"{operation_name} - {self.partner_id.name}"
        
        # Mapear operation_type del wizard a operation_type de money.flow
        money_flow_op = 'deposit' if self.operation_type == 'load' else 'withdrawal'
        
        # PASO 1: Usar el flujo central de money.flow
        # (único punto autorizado — crea wallet.transaction, actualiza balance_game y wallet.balance)
        tx = self.env['casino.money.flow'].process_operation(
            operation_type=money_flow_op,
            partner_id=self.partner_id,
            amount=self.amount,
            note=description,
            origin_model=self._name,
            origin_id=self.id,
        )
        
        # PASO 2: Crear registro administrativo de casino.game.withdrawals
        # (historial/backoffice — vinculado a la transacción real del money flow)
        withdrawal_vals = {
            'date': self.date,
            'description': description,
            'amount': self.amount,
            'partner_id': self.partner_id.id,
            'operation_type': self.operation_type,
        }
        self.env["casino.game.withdrawals"].with_context(skip_money_flow=True).create(withdrawal_vals)
        
        message = f"Operación registrada exitosamente: {operation_name} por ${self.amount:,.2f}"
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        """Cancelar y cerrar el wizard"""
        return {'type': 'ir.actions.act_window_close'}