# -*- coding: utf-8 -*-
from odoo import api, fields, models

class MaintenanceSite(models.Model):
    _name = 'maintenance.site'
    _description = 'Sitio de Mantenimiento'
    _order = 'name'
    
    name = fields.Char(
        string='Nombre del Sitio',
        required=True,
        tracking=True
    )
    
    code = fields.Char(
        string='Código',
        help='Código del sitio (ej: PERG, AD)'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    
    active = fields.Boolean(
        default=True,
        string='Activo'
    )
    
    sector_ids = fields.One2many(
        'maintenance.sector',
        'site_id',
        string='Sectores'
    )
    
    sector_count = fields.Integer(
        string='Cantidad de Sectores',
        compute='_compute_sector_count'
    )
    
    @api.depends('sector_ids')
    def _compute_sector_count(self):
        for record in self:
            record.sector_count = len(record.sector_ids)
    
    _sql_constraints = [
        ('name_company_unique', 'UNIQUE(name, company_id)', 
         'El nombre del sitio debe ser único por compañía!')
    ]


class MaintenanceSector(models.Model):
    _name = 'maintenance.sector'
    _description = 'Sector de Mantenimiento'
    _order = 'site_id, name'
    
    name = fields.Char(
        string='Nombre del Sector',
        required=True,
        tracking=True
    )
    
    code = fields.Char(
        string='Código',
        help='Código del sector'
    )
    
    site_id = fields.Many2one(
        'maintenance.site',
        string='Sitio',
        required=True,
        ondelete='cascade'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='site_id.company_id',
        store=True,
        readonly=True
    )
    
    active = fields.Boolean(
        default=True,
        string='Activo'
    )
    
    description = fields.Text(
        string='Descripción'
    )
    
    _sql_constraints = [
        ('name_site_unique', 'UNIQUE(name, site_id)', 
         'El nombre del sector debe ser único por sitio!')
    ]