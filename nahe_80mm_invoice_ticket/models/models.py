
# -*- coding: utf-8 -*-

from odoo import models, fields, api

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, RedirectWarning
import logging
import datetime
from datetime import datetime, timedelta, date
import json

try:
    from base64 import encodebytes
except ImportError:  # 3+
    from base64 import encodestring as encodebytes



# class nahe_80mm_invoice_ticket(models.Model):
#     _name = 'nahe_80mm_invoice_ticket.nahe_80mm_invoice_ticket'
#     _description = 'nahe_80mm_invoice_ticket.nahe_80mm_invoice_ticket'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _compute_json_qr(self):
        for rec in self:
            dict_invoice = ''
            if rec.move_type in ['out_invoice', 'out_refund'] and rec.state == 'posted' and rec.afip_auth_code != '':
                try:
                    dict_invoice = {
                        "ver": 1,
                        "fecha": str(rec.invoice_date),
                        "cuit": int(rec.company_id.partner_id.vat),
                        "ptoVta": rec.journal_id.l10n_ar_afip_pos_number,
                        "tipoCmp": int(rec.l10n_latam_document_type_id.code),
                        "nroCmp": int(rec.name.split('-')[2]),
                        "importe": rec.amount_total,
                        "moneda": rec.currency_id.l10n_ar_afip_code,
                        "ctz": rec.l10n_ar_currency_rate,
                        "tipoDocRec": int(rec.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code),
                        "nroDocRec": int(rec.partner_id.vat),
                        "tipoCodAut": 'E',
                        "codAut": rec.afip_auth_code,
                    }
                except:
                    dict_invoice = 'ERROR'
                    pass
                res = str(dict_invoice).replace("\n", "")
            else:
                res = 'N/A'
            rec.json_qr = res
            if type(dict_invoice) == dict:
                enc = res.encode()
                b64 = encodebytes(enc)
                b64 = encodebytes(json.dumps(dict_invoice, indent=None).encode('ascii')).decode('ascii')
                b64 = str(b64).replace("\n", "")
                rec.texto_modificado_qr = 'https://www.afip.gob.ar/fe/qr/?p=' + str(b64)
            else:
                rec.texto_modificado_qr = 'https://www.afip.gob.ar/fe/qr/?ERROR'

    json_qr = fields.Char("JSON QR AFIP", compute=_compute_json_qr)
    texto_modificado_qr = fields.Char('Texto Modificado QR', compute=_compute_json_qr)
