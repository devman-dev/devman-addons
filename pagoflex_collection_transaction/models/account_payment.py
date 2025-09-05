# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    conciliado = fields.Selection([('conciliado','Conciliado'),('no_conciliado','No conciliado')], default="no_conciliado")

    def _pagoflex_prepare_collection_ctx(self):
        """Valores por defecto para el form de collection.transaction (Odoo 17)."""
        self.ensure_one()


        partner = self.partner_id
        amount = abs(self.amount)
        payment_date = self.date or fields.Date.context_today(self)
        currency = self.currency_id or (self.company_id and self.company_id.currency_id) or False

        destination_bank = ''
        cbu = ''
        bank_model_id = False

        journal = self.journal_id
        # Si el diario apunta a tu modelo de banco personalizado, ajustá el nombre del campo:
        if hasattr(journal, "pagoflex_bank_id") and journal.pagoflex_bank_id:
            bank_model_id = journal.pagoflex_bank_id.id
            destination_bank = journal.pagoflex_bank_id.name or ''

        # Campos de cheque en el propio payment (ajustá si están en otra relación)
        check_number = getattr(self, "check_number", False)
        check_date = getattr(self, "check_date", False)
        check_deposit_date = getattr(self, "check_deposit_date", False)
        check_endorsement = getattr(self, "check_endorsement", False)
        check_bank_id = getattr(self, "check_bank", False).id if getattr(self, "check_bank", False) else False

        description = self.ref or getattr(self, 'communication', False) or (journal.display_name if journal else "") or ""
        if destination_bank:
            description = (destination_bank + " - " + description).strip(" -")

        ctx = {
            # Conciliación (si alguna vez lo disparás desde extractos)
            'default_is_concilied': False,
            'default_concilied_id': False,

            # Core
            'default_date': payment_date,
            'default_amount': amount,
            'default_customer': partner.id if partner else False,
            'conciliation_wiz': True,
            'default_description': description,

            # Tipo de movimiento
            'default_collection_trans_type': 'retiro' if destination_bank else 'movimiento_recaudacion',

            # Destino/Origen
            'default_name_destination_account': destination_bank or '',
            'default_cbu_destination_account': cbu or '',
            'default_origen_name_account_extern': (journal.name if journal else '') if not destination_bank else '',
            'default_origin_account_cbu': cbu if not destination_bank else '',

            # Vínculos
            'default_payment_id': self.id,
            'default_account_bank': bank_model_id,

            # Cheque
            'default_check_number': check_number or '',
            'default_check_date': check_date or False,
            'default_check_deposit_date': check_deposit_date or False,
            'default_check_endorsement': check_endorsement or '',
            'default_check_bank': check_bank_id or False,

            # Moneda
            'default_currency_id': currency.id if currency else False,
        }
        return ctx


    def pagoflex_open_collection_transaction_form(self):
        """Devuelve la acción que abre el form de collection.transaction como wizard."""
        self.ensure_one()
        collect_domain = [('customer', '=', self.partner_id.id),('payment_id','=', self.id)]

        pago_creado = self.env['collection.transaction'].sudo().search(collect_domain)
        if pago_creado:
            raise ValidationError('Ya existe la acreditación del cheque en PagoFlex, para volver a acreditarlo elimine el movimiento existente en PagoFlex.')

        ctx = self._pagoflex_prepare_collection_ctx()
        return {
            'name': _('Conciliación de Transacciones'),
            'type': 'ir.actions.act_window',
            'res_model': 'collec.trans.wiz',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

