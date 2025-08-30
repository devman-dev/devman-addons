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
        string="Aprobado por",
        readonly=True
    )
    approved_date = fields.Datetime(
        string="Fecha de Aprobación",
        readonly=True
    )

    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    bank_id = fields.Many2one("casino.game.bank", string="Cuenta Bancaria", required=True)
    
    def action_change_state(self):
        new_state = self.env.context.get('new_state')
        if not new_state:
            return

        vals = {'state': new_state}

        if new_state == 'approved':
            vals.update({
                'approved_by_id': self.env.uid,
                'approved_date': fields.Datetime.now(),
            })
        else:
            # Si lo desaprueban, limpiamos usuario y fecha
            vals.update({
                'approved_by_id': False,
                'approved_date': False,
            })

        self.write(vals)