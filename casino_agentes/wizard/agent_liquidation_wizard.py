# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, time

class AgentLiquidationWizard(models.TransientModel):
    _name = 'agent.liquidation.wizard'
    _description = 'Liquidación de agentes por comisiones'

    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    agent_id = fields.Many2one('res.partner', string='Agente', domain="[('is_agent','=',True)]")
    view_type = fields.Selection([
        ('tree', 'Árbol jerárquico'),
        ('table', 'Tabla simple'),
        ('wizard', 'Wizard detallado')
    ], string='Vista', default='tree', required=True)

    def action_liquidate(self):
        self.ensure_one()
        # 1) Ventana de fechas a datetimes (UTC-safe mediante fields.Datetime)
        date_from_dt = datetime.combine(self.date_from, time.min)
        date_to_dt = datetime.combine(self.date_to, time.max)

        Session = self.env['casino.game.session']
        # 2) Traer sesiones de pérdida en el rango, considerando start o end datetime
        #    Domain: (start in range) OR (end in range), con agente y comisión presentes
        domain = [
            ('result', '=', 'loss'),
            ('agent_id', '!=', False),
            ('agent_commission', '>', 0),
            '|',
                '&', ('start_datetime', '>=', fields.Datetime.to_string(date_from_dt)), ('start_datetime', '<=', fields.Datetime.to_string(date_to_dt)),
                '&', ('end_datetime', '>=', fields.Datetime.to_string(date_from_dt)), ('end_datetime', '<=', fields.Datetime.to_string(date_to_dt)),
        ]
        sessions = Session.search(domain)

        # 3) Agregar por agente en Python para evitar ambigüedades de read_group y TZ
        direct_by_agent = {}
        currency = self.env.company.currency_id
        for s in sessions:
            aid = s.agent_id.id
            amt = s.agent_commission or 0.0
            if not aid or not amt:
                continue
            direct_by_agent[aid] = currency.round((direct_by_agent.get(aid, 0.0) or 0.0) + amt)

        # 3) Determinar agentes de partida (raíz o específico)
        Partner = self.env['res.partner']
        if self.agent_id:
            roots = self.agent_id
        else:
            roots = Partner.search([('is_agent', '=', True), ('parent_agent_id', '=', False)])

        lines_vals = []

        # Cache para evitar recomputar
        totals_cache = {}

        def compute_totals(agent):
            if agent.id in totals_cache:
                return totals_cache[agent.id]
            direct = float(direct_by_agent.get(agent.id, 0.0))
            # Total de cada subagente inmediato (incluye su propia comisión de subagentes)
            child_total_sum = 0.0
            for child in agent.child_agent_ids.filtered(lambda a: a.is_agent):
                child_total = compute_totals(child)
                pct = (agent.subagent_commission_percent or 0.0) / 100.0
                if pct:
                    child_total_sum += child_total * pct
            total = direct + child_total_sum
            # Registrar línea solo si hay algo que mostrar
            if direct or child_total_sum:
                # Redondeo de importes por moneda de la compañía
                lines_vals.append({
                    'agent_id': agent.id,
                    'direct_commission': currency.round(direct),
                    'subagent_commission': currency.round(child_total_sum),
                })
            totals_cache[agent.id] = total
            return total

        # 4) Recorrer árboles
        for root in roots:
            if root.is_agent:
                compute_totals(root)

        # 5) Crear la liquidación persistente y abrirla
        liquidation = self.env['agent.liquidation'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'agent_id': self.agent_id.id if self.agent_id else False,
            'company_id': self.env.company.id,
            'line_ids': [(0, 0, vals) for vals in lines_vals],
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agent.liquidation',
            'res_id': liquidation.id,
            'view_mode': 'form',
            'target': 'current',
        }

class AgentLiquidationResult(models.TransientModel):
    _name = 'agent.liquidation.result'
    _description = 'Resultado de liquidación de agentes'
    # Reservado para futuras vistas no persistentes (no usado actualmente)
