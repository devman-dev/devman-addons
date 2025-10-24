# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    # Marcadores funcionales básicos
    is_agent = fields.Boolean(string="Es agente")
    is_player = fields.Boolean(string="Es jugador")

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

    @api.constrains("agent_id", "is_player")
    def _check_player_agent(self):
        for rec in self:
            # Si tiene un agente asignado, o está marcado como jugador, validar coherencia
            if rec.agent_id and not rec.agent_id.is_agent:
                raise ValidationError(_("El agente asignado al jugador no está marcado como agente."))
            # Evitar asignar como agente a sí mismo
            if rec.agent_id and rec.agent_id.id == rec.id:
                raise ValidationError(_("Un jugador no puede ser su propio agente."))
            # Opcional: si tiene agent_id, marcamos is_player por coherencia (sin forzar)
            if rec.agent_id and not rec.is_player:
                # No lanzamos error; mantenemos flexible. Si quieres forzarlo, cambia por ValidationError.
                pass
