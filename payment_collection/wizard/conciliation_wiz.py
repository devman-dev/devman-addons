from odoo import fields, models
from odoo.exceptions import ValidationError

class ConciliationWiz(models.TransientModel):
    _name = 'conciliation.wiz'

    collection_transaction_ids = fields.Many2many('collection.transaction', string='Transacciones')

    def confirm(self):
        if len(self.collection_transaction_ids) > 1:
            raise ValidationError('Solo puede conciliar una transacción a la vez.')
        bank_statement_id = self.env.context.get('bank_statement_id', False)
        date = self.env.context.get('date', False)
        amount = self.env.context.get('amount', False)
        titular = self.env.context.get('titular', False)
        
        destination_bank = self.env.context.get('destination_bank', False)
        bank = self.env.context.get('bank', False)
        cbu = self.env.context.get('cbu', False)
        

        if not self.collection_transaction_ids:
            customer = self.env['res.partner'].search([('name', 'ilike', f'%{titular}%')], limit=1)
            return {
                'name': 'Conciliación de Transacciones',
                'type': 'ir.actions.act_window',
                'res_model': 'collection.transaction',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_is_concilied': True,
                    'default_concilied_id': bank_statement_id,
                    'default_date': date,
                    'default_amount': amount,
                    'default_customer': customer.id,
                    'conciliation_wiz': True,
                    'default_description': str(destination_bank) + " - " + str(bank) + " - " + str(cbu),
                    'default_collection_trans_type': 'retiro' if destination_bank else 'movimiento_recaudacion', 
                    'default_name_destination_account': destination_bank if destination_bank else 'd',
                    'default_cbu_destination_account': cbu if destination_bank else '1',
                              
                },
            }
        else:
            bank_statement = self.env['bank.statement'].browse(bank_statement_id)
            for record in self.collection_transaction_ids:
                record.write({'is_concilied': True, 'concilied_id': bank_statement_id})
                bank_statement.write({'is_concilied': True,'concilied_id': record.id})
