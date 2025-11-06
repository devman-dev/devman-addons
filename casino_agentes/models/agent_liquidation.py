# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time


class AgentLiquidation(models.Model):
    _name = 'casino.agent.liquidation'
    _description = 'Liquidación de agentes'
    _order = 'create_date desc'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    agent_id = fields.Many2one('res.partner', string='Agente', domain="[('is_agent','=',True)]")

    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', related='company_id.currency_id', store=True, readonly=True)

    line_ids = fields.One2many('casino.agent.liquidation.line', 'liquidation_id', string='Líneas')

    total_direct = fields.Monetary(string='Total directo', compute='_compute_totals', currency_field='currency_id', store=True)
    total_subagents = fields.Monetary(string='Total subagentes', compute='_compute_totals', currency_field='currency_id', store=True)
    total_amount = fields.Monetary(string='Total', compute='_compute_totals', currency_field='currency_id', store=True)

    @api.depends('date_from', 'date_to', 'agent_id')
    def _compute_name(self):
        for rec in self:
            if rec.agent_id:
                rec.name = _('Liquidación %s [%s - %s]') % (
                    rec.agent_id.display_name or '', rec.date_from or '', rec.date_to or ''
                )
            else:
                rec.name = _('Liquidación [%(from)s - %(to)s]') % {
                    'from': rec.date_from or '', 'to': rec.date_to or ''
                }

    @api.depends('line_ids.direct_commission', 'line_ids.subagent_commission')
    def _compute_totals(self):
        for rec in self:
            direct = sum(rec.line_ids.mapped('direct_commission'))
            sub = sum(rec.line_ids.mapped('subagent_commission'))
            rec.total_direct = direct
            rec.total_subagents = sub
            rec.total_amount = direct + sub

    # --- Utilidades para cálculo y creación desde "Nuevo" ---
    def _prepare_lines_from_period(self, date_from, date_to, agent=None):
        """Devuelve una lista de dicts con líneas calculadas para el rango y agente raíz opcional.

        Replica la lógica del wizard para poder crear una liquidación desde el botón "Nuevo".
        """
        # Asegurar datetimes completos para el filtro
        date_from_dt = datetime.combine(date_from, time.min)
        date_to_dt = datetime.combine(date_to, time.max)

        Session = self.env['casino.game.session']
        domain = [
            ('result', '=', 'loss'),
            ('agent_id', '!=', False),
            ('agent_commission', '>', 0),
            '|',
                '&', ('start_datetime', '>=', fields.Datetime.to_string(date_from_dt)), ('start_datetime', '<=', fields.Datetime.to_string(date_to_dt)),
                '&', ('end_datetime', '>=', fields.Datetime.to_string(date_from_dt)), ('end_datetime', '<=', fields.Datetime.to_string(date_to_dt)),
        ]
        sessions = Session.search(domain)

        # Agregación por agente
        direct_by_agent = {}
        currency = self.env.company.currency_id
        for s in sessions:
            aid = s.agent_id.id
            amt = s.agent_commission or 0.0
            if not aid or not amt:
                continue
            direct_by_agent[aid] = currency.round((direct_by_agent.get(aid, 0.0) or 0.0) + amt)

        Partner = self.env['res.partner']
        roots = agent if agent else Partner.search([('is_agent', '=', True), ('parent_agent_id', '=', False)])

        lines_vals = []
        totals_cache = {}

        def compute_totals(agent_rec):
            if agent_rec.id in totals_cache:
                return totals_cache[agent_rec.id]
            direct = float(direct_by_agent.get(agent_rec.id, 0.0))
            child_total_sum = 0.0
            for child in agent_rec.child_agent_ids.filtered(lambda a: a.is_agent):
                child_total = compute_totals(child)
                pct = (agent_rec.subagent_commission_percent or 0.0) / 100.0
                if pct:
                    child_total_sum += child_total * pct
            total = direct + child_total_sum
            if direct or child_total_sum:
                lines_vals.append({
                    'agent_id': agent_rec.id,
                    'direct_commission': currency.round(direct),
                    'subagent_commission': currency.round(child_total_sum),
                })
            totals_cache[agent_rec.id] = total
            return total

        for root in roots:
            if root.is_agent:
                compute_totals(root)

        return lines_vals

    @api.model
    def create(self, vals):
        """Permitir creación desde la lista: si no se pasan líneas, las calculamos."""
        # Si el usuario crea desde "Nuevo", normalmente no habrá line_ids
        if not vals.get('line_ids'):
            date_from = vals.get('date_from')
            date_to = vals.get('date_to')
            agent_id = vals.get('agent_id')
            if date_from and date_to:
                agent = self.env['res.partner'].browse(agent_id) if agent_id else False
                # fields.Date puede venir como string, convertir a date con fields.Date.from_string
                df = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
                dt = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
                lines_vals = self._prepare_lines_from_period(df, dt, agent=agent)
                vals['line_ids'] = [(0, 0, l) for l in lines_vals]
        return super().create(vals)

    def write(self, vals):
        """Evitar modificar los filtros clave de una liquidación ya creada.

        Permite que el formulario sea editable al crear (sin attrs),
        pero bloquea cambios posteriores a date_from, date_to, agent_id y company_id.
        """
        protected = {'date_from', 'date_to', 'agent_id', 'company_id'}
        changing = protected.intersection(vals.keys())
        if changing:
            for rec in self:
                if rec.id:
                    raise UserError(_(
                        'No se pueden modificar %(campos)s en una liquidación ya creada.',
                    ) % {'campos': ', '.join(sorted(changing))})
        return super().write(vals)


class AgentLiquidationLine(models.Model):
    _name = 'casino.agent.liquidation.line'
    _description = 'Línea de liquidación de agente'
    _order = 'agent_id, id'

    liquidation_id = fields.Many2one('casino.agent.liquidation', string='Liquidación', required=True, ondelete='cascade')
    agent_id = fields.Many2one('res.partner', string='Agente', required=True, domain="[('is_agent','=',True)]")

    currency_id = fields.Many2one('res.currency', related='liquidation_id.currency_id', store=True, readonly=True)

    direct_commission = fields.Monetary(string='Comisión directa', currency_field='currency_id')
    subagent_commission = fields.Monetary(string='Comisión por subagentes', currency_field='currency_id')
    total_commission = fields.Monetary(string='Total', compute='_compute_total', currency_field='currency_id', store=True)

    @api.depends('direct_commission', 'subagent_commission')
    def _compute_total(self):
        for line in self:
            line.total_commission = (line.direct_commission or 0.0) + (line.subagent_commission or 0.0)
