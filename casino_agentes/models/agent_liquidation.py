# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AgentLiquidation(models.Model):
    _name = 'agent.liquidation'
    _description = 'Liquidación de agentes'
    _order = 'create_date desc'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    agent_id = fields.Many2one('res.partner', string='Agente', domain="[('is_agent','=',True)]")

    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', related='company_id.currency_id', store=True, readonly=True)

    line_ids = fields.One2many('agent.liquidation.line', 'liquidation_id', string='Líneas')

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


class AgentLiquidationLine(models.Model):
    _name = 'agent.liquidation.line'
    _description = 'Línea de liquidación de agente'
    _order = 'agent_id, id'

    liquidation_id = fields.Many2one('agent.liquidation', string='Liquidación', required=True, ondelete='cascade')
    agent_id = fields.Many2one('res.partner', string='Agente', required=True, domain="[('is_agent','=',True)]")

    currency_id = fields.Many2one('res.currency', related='liquidation_id.currency_id', store=True, readonly=True)

    direct_commission = fields.Monetary(string='Comisión directa', currency_field='currency_id')
    subagent_commission = fields.Monetary(string='Comisión por subagentes', currency_field='currency_id')
    total_commission = fields.Monetary(string='Total', compute='_compute_total', currency_field='currency_id', store=True)

    @api.depends('direct_commission', 'subagent_commission')
    def _compute_total(self):
        for line in self:
            line.total_commission = (line.direct_commission or 0.0) + (line.subagent_commission or 0.0)
