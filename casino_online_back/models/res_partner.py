import logging

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = "res.partner"

    is_agent = fields.Boolean(string="Es agente")
    is_player = fields.Boolean(string="Es jugador")

    password = fields.Char(
        string='Contraseña', copy=False,
        help='Se usa solo al crear un jugador. Se borra inmediatamente después de crear el usuario.')
    confirm_password = fields.Char(
        string='Confirmar Contraseña', copy=False)

    # Rol legible para vistas
    role = fields.Selection([
        ('agent', 'Agente'),
        ('player', 'Jugador'),
    ], string='Rol', compute='_compute_role', search='_search_role', store=True)

    # Agente superior unificado: para agentes -> parent_agent_id; para jugadores -> agent_id
    supervisor_agent_id = fields.Many2one(
        'res.partner', string='Agente Superior', compute='_compute_supervisor_agent', store=False)

    # Jerarquía de agentes (solo entre registros marcados como agente)
    parent_agent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Agente superior",
        domain="[('is_agent', '=', True), ('id', '!=', id)]",
        help="Agente directo del cual depende este agente."
    )
    child_agent_ids = fields.One2many(
        comodel_name="res.partner",
        inverse_name="parent_agent_id",
        string="Subagentes",
        domain=[("is_agent", "=", True)],
        help="Agentes que dependen jerárquicamente de este agente."
    )

    # Vinculación de jugadores con su agente directo
    agent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Agente",
        domain="[('is_agent', '=', True)]",
        help="Agente responsable de este jugador."
    )
    managed_player_ids = fields.One2many(
        comodel_name="res.partner",
        inverse_name="agent_id",
        string="Jugadores a cargo",
        domain=[("is_player", "=", True)],
        help="Jugadores asignados a este agente."
    )
    
    subagent_commission_percent = fields.Float(
        string='Comisión sobre subagentes (%)',
        default=10.0,
        help='Porcentaje de comisión que este agente cobra sobre el total de comisiones de sus subagentes de nivel inmediato.'
    )

    # Profundidad (opcional, útil para vistas/informes)
    agent_depth = fields.Integer(
        string="Nivel jerárquico",
        compute="_compute_agent_depth",
        store=True,
        recursive=True,
        help="Distancia hasta el tope de la jerarquía de agentes."
    )


    def _create_or_sync_user(self, partner, password, Users, portal_group, cr):
        """Create or sync res.users for a player partner. Always called for is_player+email."""
        existing_user = Users.search([('partner_id', '=', partner.id)], limit=1)
        if existing_user:
            if password:
                try:
                    existing_user.sudo().write({'password': password})
                    _logger.info(
                        "Password synced to existing res.users (login=%s) for partner_id=%s",
                        partner.email, partner.id,
                    )
                except Exception as e:
                    _logger.error(
                        "Error syncing password for partner_id=%s: %s",
                        partner.id, str(e),
                    )
            return

        # Check for duplicate login
        existing_by_login = Users.search([('login', '=', partner.email)], limit=1)
        if existing_by_login:
            _logger.warning(
                "No se pudo crear res.users para partner_id=%s: "
                "login=%s ya existe (user_id=%s). Vinculando partner...",
                partner.id, partner.email, existing_by_login.id,
            )
            existing_by_login.sudo().write({'partner_id': partner.id})
            if password:
                existing_by_login.sudo().write({'password': password})
            return

        try:
            user_vals = {
                'name': partner.name,
                'login': partner.email,
                'partner_id': partner.id,
            }
            if portal_group:
                user_vals['groups_id'] = [(6, 0, [portal_group.id])]
            new_user = Users.create(user_vals)

            if password:
                new_user.sudo().write({'password': password})
            else:
                # Generate random password when none provided (player created without pw)
                import secrets, string
                random_pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                try:
                    new_user.sudo().write({'password': random_pw})
                except Exception:
                    pass
                _logger.info(
                    "Creado res.users (login=%s) para partner_id=%s "
                    "[SIN password provisto — se generó uno aleatorio]",
                    partner.email, partner.id,
                )
                return

            cr.commit()
            _logger.info(
                "Creado res.users (login=%s) para partner_id=%s",
                partner.email, partner.id,
            )
        except Exception as e:
            _logger.error(
                "Error creando res.users para partner_id=%s: %s",
                partner.id, str(e),
            )
            cr.rollback()

    @api.model_create_multi
    def create(self, vals_list):
        # Extraer passwords antes de super() — se usan solo para crear res.users
        passwords = {}
        for i, vals in enumerate(vals_list):
            pw = vals.get('password')
            if pw:
                passwords[i] = pw

        partners = super().create(vals_list)
        BetLimits = self.env['casino.game.bet.limits'].sudo()
        default_company = self.env.company or self.env['res.company'].sudo().search([], limit=1)
        Users = self.env['res.users'].sudo()
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)

        for i, partner in enumerate(partners):
            BetLimits.get_or_create_for_partner(partner, company=default_company)

            pw = passwords.get(i)
            if pw and partner.is_player and partner.email:
                # Buscar si ya existe un res.users para este partner
                existing_user = Users.search([('partner_id', '=', partner.id)], limit=1)
                if not existing_user:
                    # También buscar por login para evitar error de duplicado
                    existing_by_login = Users.search([('login', '=', partner.email)], limit=1)
                    if existing_by_login:
                        _logger.warning(
                            "No se pudo crear res.users para partner_id=%s: "
                            "login=%s ya existe (user_id=%s). Vincular manualmente.",
                            partner.id, partner.email, existing_by_login.id,
                        )
                    else:
                        try:
                            user_vals = {
                                'name': partner.name,
                                'login': partner.email,
                                'partner_id': partner.id,
                            }
                            if portal_group:
                                user_vals['groups_id'] = [(6, 0, [portal_group.id])]
                            new_user = Users.create(user_vals)
                            # Odoo 18: password debe setearse via write (no en create vals)
                            new_user.sudo().write({'password': pw})
                            cr = self.env.cr
                            cr.commit()
                            _logger.info(
                                "Creado res.users (login=%s) para partner_id=%s",
                                partner.email, partner.id,
                            )
                        except Exception as e:
                            _logger.error(
                                "Error creando res.users para partner_id=%s: %s",
                                partner.id, str(e),
                            )
                            self.env.cr.rollback()
                # Limpiar contraseña del partner (no se almacena)
                partner.sudo().write({'password': False, 'confirm_password': False})
            elif pw and not partner.email:
                raise ValidationError(_(
                    'Se requiere un email para crear el acceso.\n'
                    'Completá el campo Email antes de asignar una contraseña.'
                ))

        return partners
    def write(self, vals):
        """Sync password changes from partner form to linked res.users."""
        pw = vals.get('password')
        if pw:
            Users = self.env['res.users'].sudo()
            for partner in self:
                if partner.is_player and partner.email:
                    user = Users.search([('partner_id', '=', partner.id)], limit=1)
                    if user:
                        try:
                            user.write({'password': pw})
                            _logger.info(
                                "Password synced to res.users (login=%s) for partner_id=%s",
                                partner.email, partner.id)
                        except Exception as e:
                            _logger.error("Error syncing password for partner_id=%s: %s",
                                          partner.id, str(e))
            # Don't store password on partner record
            vals = dict(vals)
            vals['password'] = False
            vals['confirm_password'] = False
        return super().write(vals)


    @api.depends("parent_agent_id", "parent_agent_id.agent_depth")
    def _compute_agent_depth(self):
        for rec in self:
            if rec.is_agent and rec.parent_agent_id:
                rec.agent_depth = (rec.parent_agent_id.agent_depth or 0) + 1
            elif rec.is_agent:
                rec.agent_depth = 0
            else:
                rec.agent_depth = 0

    # Reglas de consistencia
    @api.constrains("parent_agent_id", "is_agent")
    def _check_agent_hierarchy(self):
        for rec in self:
            # Si tiene padre, debe ser agente
            if rec.parent_agent_id and not rec.is_agent:
                raise ValidationError(
                    _("Solo un partner marcado como 'Es agente' puede tener 'Agente superior'.")
                )
            # El padre debe ser agente
            if rec.parent_agent_id and not rec.parent_agent_id.is_agent:
                raise ValidationError(
                    _("El 'Agente superior' seleccionado no está marcado como agente.")
                )
            # Evitar referenciarse a sí mismo
            if rec.parent_agent_id and rec.parent_agent_id.id == rec.id:
                raise ValidationError(_("Un agente no puede ser su propio agente superior."))
            # Evitar ciclos
            if not rec._check_recursion(parent="parent_agent_id"):
                raise ValidationError(_("Ciclo detectado en la jerarquía de agentes."))

    @api.constrains('password', 'confirm_password')
    def _check_password_match(self):
        for rec in self:
            if rec.password and rec.password != rec.confirm_password:
                raise ValidationError(_('Las contraseñas no coinciden.'))

    @api.constrains("agent_id", "is_player")
    def _check_player_agent(self):
        for rec in self:
            # Si tiene un agente asignado, o está marcado como jugador, validar coherencia
            if rec.agent_id and not rec.agent_id.is_agent:
                raise ValidationError(_("El agente asignado al jugador no está marcado como agente."))
            # Evitar asignar como agente a sí mismo
            if rec.agent_id and rec.agent_id.id == rec.id:
                raise ValidationError(_("Un jugador no puede ser su propio agente."))

    @api.depends('is_agent', 'is_player')
    def _compute_role(self):
        for rec in self:
            if rec.is_agent:
                rec.role = 'agent'
            elif rec.is_player:
                rec.role = 'player'
            else:
                rec.role = False

    def _search_role(self, operator, value):
        """Permite buscar por el campo role usando is_agent e is_player."""
        if operator == '=' and value == 'agent':
            return [('is_agent', '=', True)]
        elif operator == '=' and value == 'player':
            return [('is_player', '=', True)]
        elif operator == '!=' and value == 'agent':
            return [('is_agent', '=', False)]
        elif operator == '!=' and value == 'player':
            return [('is_player', '=', False)]
        elif operator == 'in' and isinstance(value, list):
            domain = []
            if 'agent' in value and 'player' in value:
                domain = ['|', ('is_agent', '=', True), ('is_player', '=', True)]
            elif 'agent' in value:
                domain = [('is_agent', '=', True)]
            elif 'player' in value:
                domain = [('is_player', '=', True)]
            return domain
        return []

    def _compute_supervisor_agent(self):
        for rec in self:
            rec.supervisor_agent_id = rec.parent_agent_id if rec.is_agent else rec.agent_id

    def action_open_load_chips_wizard(self):
        """Abrir el wizard de Carga de Fichas con el partner precargado."""
        self.ensure_one()
        view = self.env.ref('casino_online_back.view_chip_operation_wizard_form')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nueva Operación de Fichas',
            'res_model': 'chip.operation.wizard',
            'view_mode': 'form',
            'view_id': view.id,
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_operation_type': 'load',
            },
        }

    @api.model
    def cron_update_balance_game(self):
        """Cron de auditoría — compara balance_game contra contabilidad sin escribir.

        Calcula el saldo desde account.move.line y lo compara contra
        partner.balance_game. Si hay diferencias, registra un warning
        pero NO modifica ningún saldo.
        """
        partners = self.env['res.partner'].sudo().search([('token', '!=', False)])
        total_checked = 0
        total_mismatches = 0
        for partner in partners:
            company = partner.company_id or self.env.company
            domain = [
                ('company_id', '=', company.id),
                ('partner_id', '=', partner.id),
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
                ('parent_state', 'in', ['draft', 'posted']),
            ]

            lines = self.env['account.move.line'].sudo().search(domain)
            total = sum(
                float((l.amount_signed if l.amount_signed is not None else l.balance) or 0.0)
                for l in lines
            )
            accounting_balance = round(total, 2)
            current_balance = partner.balance_game

            total_checked += 1
            if accounting_balance != current_balance:
                total_mismatches += 1
                _logger.warning(
                    "CASINO AUDIT: balance_game mismatch for partner_id=%s | "
                    "balance_game=%.2f | accounting=%.2f | diff=%.2f",
                    partner.id, current_balance, accounting_balance,
                    current_balance - accounting_balance,
                )

        _logger.info(
            "CASINO AUDIT: cron_update_balance_game completed. "
            "Checked %d partners, %d mismatches detected.",
            total_checked, total_mismatches,
        )

    def cron_update_balance_game_RESPA(self):
        # Buscar todos los partners con token
        partners = self.env['res.partner'].sudo().search([('token', '!=', False)])
        for partner in partners:
            company = partner.company_id or self.env.company
            domain = [
                ('company_id', '=', company.id),
                ('partner_id', '=', partner.id),
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
                ('parent_state', 'in', ['draft', 'posted']),
            ]
            lines = self.env['account.move.line'].sudo().search(domain)
            total = sum(
                float((l.amount_signed if l.amount_signed is not None else l.balance) or 0.0)
                for l in lines
            )
            partner.balance_game = round(total, 2)