from odoo import models, fields, api


class BankStatement(models.Model):
    _name = 'bank.statement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bank Statement'
    _rec_name = 'titular'

    date = fields.Date(string='Fecha de Transacción', required=False, tracking=True)
    amount = fields.Float(string='Monto', required=False, tracking=True)
    titular = fields.Char(string='Titular', required=False, tracking=True)
    cuit = fields.Char(string='CUIT', required=False, tracking=True)
    bank = fields.Char(string='Banco Origen', required=False, tracking=True)
    cvu = fields.Char(string='CVU', required=False, tracking=True)
    cbu = fields.Char(string='CBU', required=False, tracking=True)
    alias = fields.Char(string='Alias', required=False, tracking=True)
    id_coelsa = fields.Char(string='Coelsa ID', required=False, tracking=True)
    reference = fields.Char(string='Referencia', help='Referencia adicional para la declaración.', tracking=True)
    is_concilied = fields.Boolean(string='Conciliado', defualt=False, tracking=True)
    concilied_id = fields.Many2one('collection.transaction', string='Conciliado con', tracking=True)
    destination_bank = fields.Char(string='Banco Destino', required=False, tracking=True)

    def break_conciliation(self):
        for rec in self:
            if rec.concilied_id:
                rec.concilied_id.concilied_id = False
                rec.concilied_id.is_concilied = False
                rec.concilied_id = False
                rec.is_concilied = False

    def open_wiz(self):
        condi = [('date', '=', self.date), ('is_commission', '=', False), ('is_concilied', '=', False), ('amount', '=', self.amount)]
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
                'destination_bank': self.destination_bank,
                'bank': self.bank,
                'cbu': self.cbu,
            },
        }
