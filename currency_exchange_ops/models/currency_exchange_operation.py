from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class CurrencyExchangeOperation(models.Model):
    _name = "currency.exchange.operation"
    _description = "Operación de cambio de divisas"
    _order = "date desc, id desc"

    name = fields.Char(string="Referencia", default=lambda self: self._default_name(), copy=False)
    partner_id = fields.Many2one("res.partner", string="Contacto", required=True)
    date = fields.Date(string="Fecha", default=fields.Date.context_today, required=True)
    journal_id = fields.Many2one("account.journal", string="Diario", required=False, domain=[("type","in",("cash","bank","general"))])
    
    
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    currency_company_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    amount_to_buy = fields.Monetary(string="Importe a comprar", required=True, currency_field="currency_buy_id", help="Cantidad en la moneda compradora.")
    currency_buy_id = fields.Many2one("res.currency", string="Moneda compradora", required=True)
    
    description = fields.Char(string="Descripción")
    spread_amount = fields.Monetary(string="Spread (en moneda de compañía)", currency_field="currency_company_id", default=0.0, help="Margen implícito del banco en moneda de compañía (p.ej. ARS)")

    # Tipo de cambio (de res.currency.rate) a la fecha - conversión a moneda de compañía
    rate_buy_to_company = fields.Float(string="TC (compradora -> compañía)", digits=(16, 8))
    rate_sell_to_company = fields.Float(string="TC (vendedora -> compañía)", digits=(16, 8))

    # Valores de compra/venta (en moneda de compañía), calculados
    buy_value_company = fields.Monetary(string="Valor de compra (compañía)", currency_field="currency_company_id")
    sell_value_company = fields.Monetary(string="Valor de venta (compañía)", currency_field="currency_company_id")

    # Cuentas contables (configurables por operación, con defaults desde la compañía)
    account_cash_id = fields.Many2one(
        "account.account",
        string="Cuenta Caja/Banco",
        default=lambda self: self.env.company.exchange_default_account_cash_id.id
    )
    account_inventory_id = fields.Many2one(
        "account.account",
        string="Cuenta Inventario Divisa",
        default=lambda self: self.env.company.exchange_default_account_inventory_id.id
    )
    account_spread_income_id = fields.Many2one(
        "account.account",
        string="Cuenta Ingreso Spread",
        default=lambda self: self.env.company.exchange_default_account_spread_income_id.id
    )
    account_spread_expense_id = fields.Many2one(
        "account.account",
        string="Cuenta Gasto Spread",
        default=lambda self: self.env.company.exchange_default_account_spread_expense_id.id
    )

    move_id = fields.Many2one("account.move", string="Asiento contable", readonly=True, copy=False)
    state = fields.Selection([
        ("draft","Borrador"),
        ("posted","Asentado"),
        ("cancel","Cancelado"),
    ], default="draft", string="Estado", tracking=True)

    amount_to_pay_company = fields.Monetary(
        string="Importe a pagar (moneda compañía)",
        currency_field="currency_company_id",
        compute="_compute_amount_to_pay_company",
        store=True,
        help="Importe que el cliente debe pagar en la moneda de la compañía para comprar la divisa."
    )

    move_summary = fields.Text(
        string="Resumen del asiento",
        compute="_compute_move_summary",
        store=True,
        readonly=True,
        help="Resumen legible del asiento contable generado para esta operación."
    )

    journal_buy_id = fields.Many2one(
        "account.journal",
        string="Diario de compra",
        required=True,
        domain=[("type", "in", ("cash", "bank", "general"))]
    )
    journal_pay_id = fields.Many2one(
        "account.journal",
        string="Diario de pago",
        required=True,
        domain=[("type", "in", ("cash", "bank", "general"))]
    )
    currency_pay_id = fields.Many2one(
        "res.currency",
        string="Divisa de pago",
        required=True
    )
    rate_pay_to_buy = fields.Float(
        string="Tipo de cambio (pago → compra)",
        compute="_compute_rate_pay_to_buy",
        store=True
    )
    amount_to_pay = fields.Monetary(
        string="Importe a pagar",
        currency_field="currency_pay_id"
    )
    price_seller = fields.Float(
        string="Precio vendedor",
        default=lambda self: self.env.company.price_seller_default
    )
    price_buyer = fields.Float(
        string="Precio comprador",
        default=lambda self: self.env.company.price_buyer_default
    )
    spread_amount = fields.Float(
        string="Spread",
        compute="_compute_spread_amount",
        store=True
    )

    exchange_account_buy_id = fields.Many2one(
        "account.account",
        string="Cuenta compra divisa",
        default=lambda self: self.env.company.exchange_account_buy_id.id
    )
    exchange_account_buy_counterpart_id = fields.Many2one(
        "account.account",
        string="Cuenta contrapartida compra",
        default=lambda self: self.env.company.exchange_account_buy_counterpart_id.id
    )
    exchange_account_pay_id = fields.Many2one(
        "account.account",
        string="Cuenta pago divisa",
        default=lambda self: self.env.company.exchange_account_pay_id.id
    )
    exchange_account_spread_income_id = fields.Many2one(
        "account.account",
        string="Cuenta ingreso spread",
        default=lambda self: self.env.company.exchange_account_spread_income_id.id
    )
    exchange_account_pay_counterpart_id = fields.Many2one(
        "account.account",
        string="Cuenta contrapartida pago",
        default=lambda self: self.env.company.exchange_account_pay_counterpart_id.id
    )

    account_moves_created = fields.Boolean(
        string="Asientos contables creados",
        default=False
    )
    transferred_to_collection = fields.Boolean(
        string="Transferido a Collection Transaction",
        default=False
    )

    @api.depends('price_seller', 'price_buyer')
    def _compute_spread_amount(self):
        for rec in self:
            rec.spread_amount = rec.price_seller - rec.price_buyer

    @api.depends("amount_to_buy", "rate_buy_to_company")
    def _compute_amount_to_pay_company(self):
        for rec in self:
            # Si la moneda compradora es la moneda de compañía, es simplemente amount_to_buy
            # Si no, se multiplica por el tipo de cambio
            if rec.currency_buy_id and rec.company_id and rec.amount_to_buy and rec.rate_buy_to_company:
                rec.amount_to_pay_company = rec.amount_to_buy * rec.rate_buy_to_company
            else:
                rec.amount_to_pay_company = 0.0

    @api.model
    def _default_name(self):
        seq = self.env.ref("currency_exchange_ops.seq_currency_exchange_operation", raise_if_not_found=False)
        return seq.next_by_id() if seq else _("Cambio de Divisas")

    @api.constrains("currency_buy_id")
    def _check_diff_currencies(self):
        # Elimina la comparación con currency_sell_id
        pass

    @api.onchange("partner_id")
    def _onchange_partner(self):
        # espacio para lógica futura (p.ej. límites, validaciones KYC)
        pass

    @api.onchange("company_id")
    def _onchange_company(self):
        for rec in self:
            if rec.company_id:
                c = rec.company_id
                rec.account_cash_id = c.exchange_default_account_cash_id
                rec.account_inventory_id = c.exchange_default_account_inventory_id
                rec.account_spread_income_id = c.exchange_default_account_spread_income_id
                rec.account_spread_expense_id = c.exchange_default_account_spread_expense_id

    @api.onchange("amount_to_buy", "currency_buy_id", "currency_sell_id", "date", "spread_amount")
    def _onchange_calculate_values(self):
        for rec in self:
            rec._compute_rates_and_values()

    def _compute_rates_and_values(self):
        for rec in self:
            if not (rec.currency_buy_id and rec.company_id and rec.date and rec.amount_to_buy):
                rec.rate_buy_to_company = 0.0
                rec.rate_sell_to_company = 0.0
                rec.buy_value_company = 0.0
                rec.sell_value_company = 0.0
                continue

            company_currency = rec.company_id.currency_id
            # Obtiene tasas a fecha (compradora -> compañía) y (vendedora -> compañía)
            rate_buy = rec.currency_buy_id._get_conversion_rate(rec.currency_buy_id, company_currency, rec.company_id, rec.date)
            #rate_sell = rec.currency_sell_id._get_conversion_rate(rec.currency_sell_id, company_currency, rec.company_id, rec.date)


            rate_sell = rec.currency_buy_id._get_conversion_rate(rec.currency_buy_id, company_currency, rec.company_id, rec.date)





            rec.rate_buy_to_company = rate_buy
            rec.rate_sell_to_company = rate_sell

            # amount_to_buy se expresa en moneda compradora
            # Valor de compra (lo que el banco recibe del cliente) en moneda de compañía
            buy_value = rec.amount_to_buy * rate_buy
            # Valor de venta (lo que el banco entrega al cliente) en moneda de compañía SIN spread
            # Para el neto, el spread ajusta el precio final
            sell_value = rec.amount_to_buy * rate_sell

            # Guardamos valores base; el asiento aplicará el spread según el sentido del flujo:
            rec.buy_value_company = buy_value
            rec.sell_value_company = sell_value

    def action_post(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Solo se pueden asentar operaciones en estado Borrador."))

            # Asiento de compra
            move_buy_vals = {
                "ref": rec.name + " (Compra)",
                "date": rec.date,
                "journal_id": rec.journal_buy_id.id,
                "line_ids": [
                    (0, 0, {
                        "name": _("Compra divisa"),
                        "account_id": rec.company_id.exchange_account_buy_id.id,
                        "debit": rec.amount_to_buy,
                        "credit": 0.0,
                        "currency_id": rec.currency_buy_id.id,
                        "partner_id": rec.partner_id.id,
                    }),
                    (0, 0, {
                        "name": _("Contrapartida compra"),
                        "account_id": rec.company_id.exchange_account_buy_counterpart_id.id,
                        "debit": 0.0,
                        "credit": rec.amount_to_buy,
                        "currency_id": rec.currency_buy_id.id,
                        "partner_id": rec.partner_id.id,
                    }),
                ],
            }
            move_buy = self.env["account.move"].create(move_buy_vals)
            move_buy.action_post()

            # Asiento de pago
            line_pay = [
                {
                    "name": _("Pago divisa"),
                    "account_id": rec.company_id.exchange_account_pay_id.id,
                    "debit": rec.amount_to_pay,
                    "credit": 0.0,
                    "currency_id": rec.currency_pay_id.id,
                    "partner_id": rec.partner_id.id,
                },
                {
                    "name": _("Spread"),
                    "account_id": rec.company_id.exchange_account_spread_income_id.id,
                    "debit": 0.0,
                    "credit": rec.spread_amount,
                    "currency_id": rec.currency_pay_id.id,
                    "partner_id": rec.partner_id.id,
                },
            ]
            total_debit = rec.amount_to_pay
            total_credit = rec.spread_amount
            # Contrapartida para cuadrar
            difference = round(total_debit - total_credit, 2)
            if abs(difference) > 0:
                line_pay.append({
                    "name": _("Contrapartida pago"),
                    "account_id": rec.company_id.exchange_account_pay_counterpart_id.id,
                    "debit": 0.0,
                    "credit": difference,
                    "currency_id": rec.currency_pay_id.id,
                    "partner_id": rec.partner_id.id,
                })

            move_pay_vals = {
                "ref": rec.name + " (Pago)",
                "date": rec.date,
                "journal_id": rec.journal_pay_id.id,
                "line_ids": [(0, 0, lv) for lv in line_pay],
            }
            move_pay = self.env["account.move"].create(move_pay_vals)
            move_pay.action_post()

            rec.move_id = move_buy.id
            rec.state = "posted"
            rec.account_moves_created = True  # <-- Agrega esta línea

    def action_reset_to_draft(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                rec.move_id.button_draft()
                rec.move_id.button_cancel()
                rec.move_id.unlink()
            rec.move_id = False
            rec.state = "draft"

    def action_cancel(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                rec.move_id.button_draft()
                rec.move_id.button_cancel()
            rec.state = "cancel"

        total_debit = sum(lv['debit'] for lv in line_vals)
        total_credit = sum(lv['credit'] for lv in line_vals)
        difference = round(total_debit - total_credit, 2)

        # Calcula totales y diferencia
        total_debit = sum(lv['debit'] for lv in line_vals)
        total_credit = sum(lv['credit'] for lv in line_vals)
        difference = round(total_debit - total_credit, 2)

        # Construye el texto del asiento
        asiento_texto = "Detalle del asiento:\n"
        for lv in line_vals:
            asiento_texto += (
                f"{lv['name']}: Cuenta {lv['account_id']} | Débito: {lv['debit']} | Crédito: {lv['credit']}\n"
            )
        total_debit = sum(lv['debit'] for lv in line_vals)
        total_credit = sum(lv['credit'] for lv in line_vals)
        difference = round(total_debit - total_credit, 2)
        asiento_texto += f"\nTotal Débito: {total_debit}\nTotal Crédito: {total_credit}\nDiferencia: {difference}"

        #raise UserError(asiento_texto)

        if abs(difference) > 0:
            adjustment_account = rec.journal_id.default_account_id.id
            if not adjustment_account:
                raise UserError(_("El asiento no está balanceado y el diario no tiene cuenta por defecto configurada."))
            line_vals.append({
                "name": _("Ajuste automático"),
                "account_id": adjustment_account,
                "debit": difference if difference > 0 else 0.0,
                "credit": -difference if difference < 0 else 0.0,
                "partner_id": rec.partner_id.id,
                "currency_id": company_currency.id,
            })

        move_vals = {
            "ref": rec.name,
            "date": rec.date,
            "journal_id": rec.journal_id.id,
            "line_ids": [(0, 0, lv) for lv in line_vals],
        }
        move = self.env["account.move"].create(move_vals)
        move.action_post()

        rec.move_id = move.id
        rec.state = "posted"

    @api.depends("move_id")
    def _compute_move_summary(self):
    
        #raise UserError(1)
    
        for rec in self:
            if rec.move_id:
                lines = []
                for line in rec.move_id.line_ids:
                    lines.append(
                        f"{line.name}: {line.account_id.display_name} | Débito: {line.debit} | Crédito: {line.credit} | Moneda: {line.currency_id.name or ''}"
                    )
                rec.move_summary = "\n".join(lines)
            else:
                rec.move_summary = ""

    @api.depends("currency_pay_id", "currency_buy_id", "date")
    def _compute_rate_pay_to_buy(self):
        for rec in self:
            if rec.currency_pay_id and rec.currency_buy_id and rec.date:
                rec.rate_pay_to_buy = rec.currency_pay_id._get_conversion_rate(
                    rec.currency_pay_id, rec.currency_buy_id, rec.company_id, rec.date
                )
            else:
                rec.rate_pay_to_buy = 0.0

    @api.depends("amount_to_buy", "rate_pay_to_buy")
    def _compute_prices(self):
        for rec in self:
            rec.price_seller = rec.rate_pay_to_buy
            rec.price_buyer = rec.rate_pay_to_buy  # Puedes ajustar si tienes lógica diferente

    @api.depends("price_buyer", "price_seller", "amount_to_buy")
    def _compute_spread(self):
        for rec in self:
            rec.spread_amount = (rec.price_buyer * rec.amount_to_buy) - (rec.price_seller * rec.amount_to_buy)

    @api.onchange("price_seller", "amount_to_buy")
    def _onchange_amount_to_pay(self):
        if self.price_seller and self.amount_to_buy:
            self.amount_to_pay = self.price_seller * self.amount_to_buy

    def create(self, vals):
        if not vals.get("amount_to_pay") and vals.get("price_seller") and vals.get("amount_to_buy"):
            vals["amount_to_pay"] = vals["price_seller"] * vals["amount_to_buy"]
        return super().create(vals)

    def write(self, vals):
        if (
            ("price_seller" in vals or "amount_to_buy" in vals)
            and not vals.get("amount_to_pay")
        ):
            price_seller = vals.get("price_seller", self.price_seller)
            amount_to_buy = vals.get("amount_to_buy", self.amount_to_buy)
            vals["amount_to_pay"] = price_seller * amount_to_buy
        return super().write(vals)

    def action_create_account_moves(self):
        for rec in self:
            # Asiento de compra de divisa
            move_buy = rec.env['account.move'].create({
                'journal_id': rec.journal_buy_id.id,
                'date': rec.date,
                'ref': f'Compra divisa {rec.currency_buy_id.name}',
                'line_ids': [
                    (0, 0, {
                        'account_id': rec.exchange_account_buy_id.id,
                        'debit': rec.amount_to_buy,
                        'credit': 0,
                        'name': 'Compra divisa',
                        'currency_id': rec.currency_buy_id.id,  # <-- Agrega esto
                    }),
                    (0, 0, {
                        'account_id': rec.exchange_account_buy_counterpart_id.id,
                        'debit': 0,
                        'credit': rec.amount_to_buy,
                        'name': 'Contrapartida compra',
                        'currency_id': rec.currency_buy_id.id,  # <-- Agrega esto
                    }),
                ]
            })

            # Asiento de pago
            # Calcula el resto para que cuadre el asiento
            spread = rec.spread_amount
            resto = rec.amount_to_pay - spread if rec.amount_to_pay and spread else 0.0

            move_pay = rec.env['account.move'].create({
                'journal_id': rec.journal_pay_id.id,
                'date': rec.date,
                'ref': f'Pago divisa {rec.currency_pay_id.name}',
                'line_ids': [
                    (0, 0, {
                        'account_id': rec.exchange_account_pay_id.id,
                        'debit': rec.amount_to_pay,
                        'credit': 0,
                        'name': 'Pago divisa',
                        'currency_id': rec.currency_pay_id.id,  # <-- Agrega esto
                    }),
                    (0, 0, {
                        'account_id': rec.exchange_account_spread_income_id.id,
                        'debit': 0,
                        'credit': spread,
                        'name': 'Ingreso spread',
                        'currency_id': rec.currency_pay_id.id,  # <-- Agrega esto
                    }),
                    (0, 0, {
                        'account_id': rec.exchange_account_pay_counterpart_id.id,
                        'debit': 0,
                        'credit': resto,
                        'name': 'Contrapartida pago',
                        'currency_id': rec.currency_pay_id.id,  # <-- Agrega esto
                    }),
                ]
            })

            self.account_moves_created = True

    def action_transfer_to_collection(self):
        for rec in self:
            if rec.transferred_to_collection:
                raise UserError(_("Este registro ya fue transferido a Collection Transaction."))

            vals = {
                'amount': rec.amount_to_pay,
                'date': rec.date,
                'description': rec.description or rec.name,
                'count': 1,
                'customer': rec.partner_id.id,
                'customer_destination': rec.partner_id.id,
                'collection_trans_type': 'movimiento_interno',
                'collection_trans_type_dest': 'movimiento_recaudacion',
                'service_dest': 1,
                'commission_dest': 0.0,
                'transaction_name': rec.name or f'Cambio de divisa {rec.id}',  # <-- Agrega este campo obligatorio
            }
            
            # Agrega campos opcionales solo si existen
            if hasattr(self.env['collection.transaction'], 'currency_id'):
                vals['currency_id'] = rec.currency_pay_id.id
                
            collection = self.env['collection.transaction'].create(vals)
            rec.transferred_to_collection = True
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Collection Transaction'),
                'res_model': 'collection.transaction',
                'view_mode': 'form',
                'res_id': collection.id,
                'target': 'current',
            }
