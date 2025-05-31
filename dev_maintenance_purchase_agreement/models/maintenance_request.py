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
from odoo.exceptions import ValidationError

class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    def create_purchase_agreement(self):
        if not self.vendor_id:
            raise ValidationError(_('''Select Vendor !'''))
        line_ids = []
        if self.plan_material_ids:
            for line_id in self.plan_material_ids:
                line_ids.append((0, 0, {'product_id': line_id.product_id and line_id.product_id.id or False,
                                        'product_qty': line_id.quantity,
                                        'price_unit': line_id.product_id and line_id.product_id.list_price,
                                        'product_uom_id':line_id.uom_id and line_id.uom_id.id or False}))
        vals = {'user_id': self.user_id and self.user_id.id or False,
                'vendor_id': self.vendor_id and self.vendor_id.id or False,
                'maintenance_request_id': self.id,
                'line_ids': line_ids,
                }
        self.env['purchase.requisition'].create(vals)

    def view_purchase_requisition(self):
        agreement_ids = self.env['purchase.requisition'].search([('maintenance_request_id', '=', self.id)])
        action = self.env["ir.actions.actions"]._for_xml_id("purchase_requisition.action_purchase_requisition")
        if len(agreement_ids) > 1:
            action['domain'] = [('id', 'in', agreement_ids.ids)]
        elif len(agreement_ids) == 1:
            action['views'] = [(self.env.ref('purchase_requisition.view_purchase_requisition_form').id, 'form')]
            action['res_id'] = agreement_ids[0].id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.onchange('equipment_id')
    def onchange_equipment_id(self):
        if self.equipment_id:
            if self.equipment_id.plan_material_ids:
                data = []
                self.plan_material_ids = [(6, 0, [])]
                for line in self.equipment_id.plan_material_ids:
                    data.append((0, 0, {'product_id': line.product_id and line.product_id.id or False,
                                        'uom_id': line.uom_id and line.uom_id.id or False,
                                        'quantity': line.quantity}))
                if data:
                    self.plan_material_ids = data
                else:
                    self.plan_material_ids = [(6, 0, [])]

    def _compute_agreement_count(self):
        for rec in self:
            agreement_ids = self.env['purchase.requisition'].search([('maintenance_request_id', '=', rec.id)])
            rec.agreement_count = len(agreement_ids)

    plan_material_ids = fields.One2many('maintenance.plan.material', 'maintenance_id', string='Maintenance Plan Material')
    vendor_id = fields.Many2one('res.partner', string='Vendor', copy=False)
    agreement_count = fields.Integer(string='Agreement', compute='_compute_agreement_count')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
