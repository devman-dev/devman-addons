import uuid

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    daily_deposit_limit = fields.Float(string='Límite diario de depósito')
    weekly_deposit_limit = fields.Float(string='Límite semanal de depósito')
    monthly_deposit_limit = fields.Float(string='Límite mensual de depósito')
    
    account_number = fields.Char('Cuenta Bancaria')
    bank_name = fields.Char('Banco')
    account_type = fields.Char('Tipo de Cuenta')
    cbu = fields.Char('CBU')
    cuil = fields.Char('CUIL')
    nuevo_cbu = fields.Char('Nuevo CBU')
    token = fields.Char(
        string='Token',
        default=lambda self: uuid.uuid4().hex,
        copy=False,
        index=True,
    )
    secret_token = fields.Char(
        string='Token Secreto',
        default=lambda self: uuid.uuid4().hex,
        copy=False,
        index=True,
    )
    nickname = fields.Char(string='Nickname')
    balance_game = fields.Float(string='Balance de los Juego')

    @api.model
    def _generate_unique_token(self, field_name='token'):
        while True:
            candidate = uuid.uuid4().hex
            if not self.search_count([(field_name, '=', candidate)]):
                return candidate

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = self._generate_unique_token('token')
            if not vals.get('secret_token'):
                vals['secret_token'] = self._generate_unique_token('secret_token')
        return super().create(vals_list)

    @api.model
    def ensure_unique_tokens(self):
        partners = self.sudo().with_context(active_test=False).search([])
        for partner in partners:
            if not partner.token or self.search_count([('token', '=', partner.token)]) > 1:
                partner.token = self._generate_unique_token('token')
            if not partner.secret_token or self.search_count([('secret_token', '=', partner.secret_token)]) > 1:
                partner.secret_token = self._generate_unique_token('secret_token')

    def website_wallet_balance(self):
        """Devuelve el saldo (float) a mostrar en el header del Website.
        Calcula la suma de movimientos de cuentas de tipo por cobrar/pagar
        del partner comercial en la compañía actual.
        """
        # Este método debe estar alineado con el método cron_update_balance_game y my/home
        
        self_sudo = self.sudo()
        partner = self_sudo.commercial_partner_id
        # company = self.env.company
        company = self.env['website'].get_current_website().company_id
        # AML = self.env['account.move.line'].sudo()
        AML = self.env['account.move.line'].sudo().with_company(company)
        domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('parent_state', 'in', ['draft', 'posted', 'in_process']),
        ]
        
        # Filtrar solo movimientos del journal de custodia si está configurado
        # if company.casino_custodia_journal_id:
        #     domain.append(('move_id.journal_id', '=', company.casino_custodia_journal_id.id))
        
        lines = AML.search(domain)
        total = sum(float((l.amount_signed if l.amount_signed is not None else l.balance) or 0.0) for l in lines)

        # AP = self.env['account.payment'].sudo().with_company(company)
        # domain_payments = [
        #     ('company_id', '=', company.id),
        #     ('partner_id', '=', partner.id),
        #     ('state', 'in', ['in_process', 'paid']),
        #         ('casino_operation_type', 'in', ['deposit', 'withdrawal']),
        # ]
        return round(total, 2)

    def _deposit_payments_fields(self):
        return [
            "date",
            "memo",
            "payment_reference",
            "amount",
            "currency_id",
        ]

    def get_deposit_payments(self):
        AccountPayment = self.env["account.payment"].sudo()
        self_sudo = self.sudo()
        domain = [
            # ("payment_type", "in", ["inbound"]),
            ("state", "in", ("in_process", "paid")),
            ("partner_id", "=", self_sudo.id),
            # ("move_id", "!=", False),
            # ("casino_operation_type", "=", "deposit")
        ]
        payments = AccountPayment.search_read(domain, self._deposit_payments_fields())
        for payment in payments:
            payment["date"] = payment["date"].strftime("%d-%m-%Y")
        return payments
