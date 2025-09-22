# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class CrmLead(models.Model):
    _inherit = "crm.lead"

    pqf_quotation_id = fields.Many2one("project.quotation", string="Cotización de Proyecto", readonly=True, copy=False)

    def action_create_project_quotation(self):
        self.ensure_one()
        quotation = self.env["project.quotation"].create({
            "lead_id": self.id,
            "name": self.name or _("Cotización"),
            "partner_id": self.partner_id.id,
        })
        self.pqf_quotation_id = quotation.id
        action = self.env.ref("project_quotation_financing.action_project_quotation").read()[0]
        action["res_id"] = quotation.id
        action["view_mode"] = "form"
        return action