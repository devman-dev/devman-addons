# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api, _


class MaintenancePlanMaterial(models.Model):
    _name = 'maintenance.plan.material'
    _description = 'Maintenance Plan Material'

    @api.onchange('product_id')
    def onchange_uom(self):
        if self.product_id and self.product_id.uom_id:
            self.uom_id = self.product_id.uom_id.id

    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment') #link
    maintenance_id = fields.Many2one('maintenance.request', string='Maintenance Request') #link
    product_id = fields.Many2one('product.product', string='Product', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Integer(string='Quantity', default=1)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: