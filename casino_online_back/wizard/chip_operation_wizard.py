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
        """Confirmar y crear la operación"""
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
        
        # Crear el registro (el transaction_id y estado se generan automáticamente en el modelo)
        vals = {
            'date': self.date,
            'description': description,
            'amount': self.amount,
            'partner_id': self.partner_id.id,
            'operation_type': self.operation_type,
        }
        
        withdrawal = self.env['casino.game.withdrawals'].create(vals)
        
        # Mostrar mensaje de éxito
        message = f"Operación registrada exitosamente: {operation_name} por ${self.amount:,.2f}"
        self.env.user.notify_success(message=message, title="¡Operación Completada!")
        
        # Retornar acción para volver al listado
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte de Fichas',
            'res_model': 'casino.game.withdrawals',
            'view_mode': 'list,form',
            'views': [(self.env.ref('casino_online_back.view_casino_withdrawals_tree').id, 'list')],
            'domain': [('operation_type', 'in', ['load', 'withdrawal']), ('bank_id', '=', False)],
            'target': 'current',
        }

    def action_cancel(self):
        """Cancelar y cerrar el wizard"""
        return {'type': 'ir.actions.act_window_close'}
        