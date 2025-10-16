from odoo import models, fields

class CasinoGameWithdrawals(models.Model):
    _name = 'casino.game.withdrawals'
    _description = 'Withdrawals'
    _order = "id desc"

    transaction_id = fields.Char(string='Transaction ID', required=True)
    date = fields.Datetime(string='Fecha', required=True)
    description = fields.Char(string='Descripción')
    amount = fields.Float(string='Monto', required=True)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Estado', default='pending')
    approved_by_id = fields.Many2one(
        comodel_name='res.users',
        string="Resuelto por",
        readonly=True
    )
    approved_date = fields.Datetime(
        string="Fecha Resolución",
        readonly=True
    )

    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    bank_id = fields.Many2one("casino.game.bank", string="Cuenta Bancaria")
    
    def action_change_state(self):
        new_state = self.env.context.get('new_state')
        if not new_state:
            return

        vals = {'state': new_state}

        if new_state == 'approved' or new_state == 'rejected':
            vals.update({
                'approved_by_id': self.env.uid,
                'approved_date': fields.Datetime.now(),
            })
            self.write(vals)
