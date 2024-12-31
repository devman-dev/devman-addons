from odoo import models, fields, api


class BankStatement(models.Model):
    _name = 'bank.statement'
    _description = 'Bank Statement'
    _rec_name = 'titular'

    date = fields.Date(string='Fecha de Transacción', required=False)
    amount = fields.Float(string='Monto', required=False)
    titular = fields.Char(string='Titular', required=False)
    cuit = fields.Char(string='CUIT', required=False)
    bank = fields.Char(string='Banco Origen', required=False)
    cvu = fields.Char(string='CVU', required=False)
    cbu = fields.Char(string='CBU', required=False)
    alias = fields.Char(string='Alias', required=False)
    id_coelsa = fields.Char(string='Coelsa ID', required=False)
    reference = fields.Char(string='Referencia', help='Referencia adicional para la declaración.')
    is_concilied = fields.Boolean(string='Conciliado', defualt=False)
    concilied_id = fields.Many2one('collection.transaction', string='Conciliado con')
    destination_bank = fields.Char(string='Banco Destino', required=False)

    def open_wiz(self):
        condi = [('date', '=', self.date),('is_commission', '=', False), ('is_concilied', '=', False),('amount','=',self.amount)]
        if not self.env.context.get('without_titular', False):
            condi.append(('customer.name', 'ilike', f'%{self.titular}%'))
            
        records = self.env['collection.transaction'].sudo().search(condi)
        
        return {
            'name': 'Conciliación de Transacciones',
            'type': 'ir.actions.act_window',
            'res_model': 'conciliation.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_collection_transaction_ids': records.ids,
                'bank_statement_id': self.id,
                'date': self.date,
                'amount': self.amount,
                'titular': self.titular,
                'destination_bank':self.destination_bank,
                'bank':self.bank,
                'cbu':self.cbu,    
                
            },
        }
