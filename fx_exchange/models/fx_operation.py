from odoo import models, fields, api
from odoo.exceptions import UserError

class FxOperation(models.Model):
    _name = 'fx.operation'
    _description = 'Foreign Exchange Operation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Operation Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    
    date = fields.Date(
        string='Operation Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    # ==================== CAMPO CONTACTO ====================
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        domain="[('is_company', '=', False)]",
        help="Contact associated with this FX operation",
        tracking=True
    )
    
    partner_email = fields.Char(
        string='Contact Email',
        related='partner_id.email',
        readonly=True,
        store=True
    )
    
    partner_phone = fields.Char(
        string='Contact Phone',
        related='partner_id.phone',
        readonly=True,
        store=True
    )
    
    partner_company = fields.Many2one(
        'res.partner',
        string='Contact Company',
        related='partner_id.parent_id',
        readonly=True,
        store=True
    )
    
    # ==================== CAMPOS DE DIVISA ====================
    currency_from = fields.Many2one(
        'res.currency',
        string='From Currency',
        required=True,
        tracking=True
    )
    
    currency_to = fields.Many2one(
        'res.currency',
        string='To Currency',
        required=True,
        tracking=True
    )
    
    amount_from = fields.Float(
        string='Amount From',
        required=True,
        digits='Product Price',
        tracking=True
    )
    
    amount_to = fields.Float(
        string='Amount To',
        required=True,
        digits='Product Price',
        tracking=True
    )
    
    exchange_rate = fields.Float(
        string='Exchange Rate',
        required=True,
        digits=(12, 6),
        tracking=True
    )
    
    # ==================== CAMPOS CONTABLES NUEVOS ====================
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        tracking=True,
        help="Accounting entry for this FX operation"
    )
    
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain="[('type', 'in', ['general', 'bank', 'cash'])]",
        help="Journal for the accounting entries"
    )
    
    commission_amount = fields.Float(
        string='Commission Amount',
        digits='Product Price',
        compute='_compute_commission_amount',
        store=True,
        help="Commission calculated based on configuration"
    )
    
    spread_amount = fields.Float(
        string='Spread Amount',
        digits='Product Price',
        help="Spread/margin for the operation"
    )
    
    # ==================== CUENTAS CONTABLES ====================
    account_from_id = fields.Many2one(
        'account.account',
        string='From Account',
        help="Account for the currency being sold"
    )
    
    account_to_id = fields.Many2one(
        'account.account',
        string='To Account',
        help="Account for the currency being bought"
    )
    
    income_account_id = fields.Many2one(
        'account.account',
        string='Income Account',
        help="Account for commission/spread income"
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('posted', 'Posted'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='State', default='draft', required=True, tracking=True)
    
    notes = fields.Text(string='Notes')
    
    # ==================== CAMPOS COMPUTADOS ====================
    partner_display_name = fields.Char(
        string='Contact Full Name',
        compute='_compute_partner_display_name',
        store=True
    )
    
    move_line_ids = fields.One2many(
        'account.move.line',
        related='move_id.line_ids',
        string='Journal Items',
        readonly=True
    )
    
    @api.depends('partner_id.name', 'partner_id.parent_id.name')
    def _compute_partner_display_name(self):
        for record in self:
            if record.partner_id:
                if record.partner_id.parent_id:
                    record.partner_display_name = f"{record.partner_id.name} ({record.partner_id.parent_id.name})"
                else:
                    record.partner_display_name = record.partner_id.name
            else:
                record.partner_display_name = ""

    @api.depends('amount_from')
    def _compute_commission_amount(self):
        for record in self:
            commission_percent = float(self.env['ir.config_parameter'].sudo().get_param(
                'fx_exchange.commission_percent', 0.0))
            record.commission_amount = record.amount_from * (commission_percent / 100)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('fx.operation') or 'New'
        
        # Obtener configuraciones por defecto
        if not vals.get('journal_id'):
            default_journal = self.env['ir.config_parameter'].sudo().get_param('fx_exchange.default_journal_id')
            if default_journal:
                vals['journal_id'] = int(default_journal)
        
        result = super(FxOperation, self).create(vals)
        
        # Mensaje automático al crear
        result.message_post(
            body=f"FX Operation {result.name} created for contact {result.partner_id.name}",
            message_type='notification'
        )
        return result
    
    @api.onchange('amount_from', 'exchange_rate')
    def _onchange_calculate_amount_to(self):
        if self.amount_from and self.exchange_rate:
            self.amount_to = self.amount_from * self.exchange_rate
    
    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        """Configurar cuentas por defecto basadas en el journal"""
        if self.journal_id:
            if self.journal_id.type in ['bank', 'cash']:
                self.account_from_id = self.journal_id.default_account_id
    
    # ==================== VALIDACIONES ====================
    @api.constrains('partner_id')
    def _check_partner_id(self):
        for record in self:
            if record.partner_id and record.partner_id.is_company:
                raise UserError("Please select an individual contact, not a company.")

    @api.constrains('amount_from', 'amount_to', 'exchange_rate')
    def _check_amounts(self):
        for record in self:
            if record.amount_from <= 0:
                raise UserError("Amount From must be greater than 0")
            if record.amount_to <= 0:
                raise UserError("Amount To must be greater than 0")
            if record.exchange_rate <= 0:
                raise UserError("Exchange Rate must be greater than 0")

    # ==================== MÉTODOS DE ACCIÓN ====================
    
    def action_confirm(self):
        """Confirmar la operación FX"""
        for record in self:
            if record.state != 'draft':
                raise UserError("Solo se pueden confirmar operaciones en estado borrador.")
            if not record.amount_from or not record.exchange_rate:
                raise UserError("Debe completar el monto y la tasa de cambio.")
            if not record.partner_id:
                raise UserError("Debe seleccionar un contacto para la operación.")
            if not record.journal_id:
                raise UserError("Debe seleccionar un diario contable.")
            
            record.state = 'confirmed'
            
            # Mensaje automático al confirmar
            record.message_post(
                body=f"FX Operation {record.name} confirmed. Exchange: {record.amount_from} {record.currency_from.name} → {record.amount_to} {record.currency_to.name}",
                message_type='notification'
            )
        return True

    def action_post(self):
        """Crear y asentar el asiento contable"""
        for record in self:
            if record.state not in ['confirmed']:
                raise UserError("Solo se pueden asentar operaciones confirmadas.")
            if not record.amount_from or not record.exchange_rate:
                raise UserError("Debe completar el monto y la tasa de cambio.")
            if not record.journal_id:
                raise UserError("Debe seleccionar un diario contable.")
            
            # Crear el asiento contable
            move = record._create_accounting_entry()
            if move:
                move.action_post()
                record.move_id = move.id
                record.state = 'posted'
                
                # Mensaje automático al crear asiento
                record.message_post(
                    body=f"Accounting entry {move.name} created and posted for FX Operation {record.name}",
                    message_type='notification'
                )
        return True

    def action_done(self):
        """Completar la operación FX"""
        for record in self:
            if record.state != 'posted':
                raise UserError("Solo se pueden completar operaciones con asiento asentado.")
            
            record.state = 'done'
            
            # Mensaje automático al completar
            record.message_post(
                body=f"FX Operation {record.name} completed successfully!",
                message_type='notification'
            )
            
            # Crear actividad para el contacto
            record._create_contact_activity()
        return True

    def action_reset_to_draft(self):
        """Volver a borrador"""
        for record in self:
            if record.state not in ['confirmed']:
                raise UserError("Solo se pueden pasar a borrador operaciones confirmadas.")
            if record.move_id:
                raise UserError("No se puede volver a borrador una operación con asiento contable. Cancele el asiento primero.")
            
            record.state = 'draft'
            
            # Mensaje automático al resetear
            record.message_post(
                body=f"FX Operation {record.name} reset to draft",
                message_type='notification'
            )
        return True

    def action_cancel(self):
        """Cancelar la operación"""
        for record in self:
            if record.state not in ['draft', 'confirmed']:
                raise UserError("Solo se pueden cancelar operaciones en borrador o confirmadas.")
            if record.move_id and record.move_id.state == 'posted':
                raise UserError("No se puede cancelar una operación con asiento asentado. Revierta el asiento primero.")
            
            # Cancelar asiento si existe
            if record.move_id:
                record.move_id.button_cancel()
            
            record.state = 'cancelled'
            
            # Mensaje automático al cancelar
            record.message_post(
                body=f"FX Operation {record.name} cancelled",
                message_type='comment'
            )
        return True
    
    # ==================== MÉTODOS CONTABLES ====================
    
    def _create_accounting_entry(self):
        """Crear el asiento contable para la operación FX"""
        self.ensure_one()
        
        # Obtener configuraciones
        company = self.env.company
        company_currency = company.currency_id
        
        # Configurar cuentas por defecto si no están definidas
        self._set_default_accounts()
        
        if not self.account_from_id or not self.account_to_id:
            raise UserError("Debe configurar las cuentas contables para la operación.")
        
        # Convertir montos a moneda de la compañía
        amount_from_company = self.currency_from._convert(
            self.amount_from, company_currency, company, self.date)
        amount_to_company = self.currency_to._convert(
            self.amount_to, company_currency, company, self.date)
        
        # Preparar líneas del asiento
        line_ids = []
        
        # Línea 1: Débito (venta de divisa FROM)
        debit_vals = {
            'name': f'FX Sale: {self.amount_from} {self.currency_from.name}',
            'account_id': self.account_from_id.id,
            'partner_id': self.partner_id.id,
            'debit': amount_from_company,
            'credit': 0.0,
        }
        
        # Configurar moneda para línea de débito
        if self.currency_from != company_currency:
            debit_vals.update({
                'currency_id': self.currency_from.id,
                'amount_currency': self.amount_from,
            })
        else:
            debit_vals.update({
                'currency_id': company_currency.id,
                'amount_currency': amount_from_company,
            })
        
        line_ids.append((0, 0, debit_vals))
        
        # Línea 2: Crédito (compra de divisa TO)
        credit_vals = {
            'name': f'FX Purchase: {self.amount_to} {self.currency_to.name}',
            'account_id': self.account_to_id.id,
            'partner_id': self.partner_id.id,
            'debit': 0.0,
            'credit': amount_to_company,
        }
        
        # Configurar moneda para línea de crédito
        if self.currency_to != company_currency:
            credit_vals.update({
                'currency_id': self.currency_to.id,
                'amount_currency': -self.amount_to,
            })
        else:
            credit_vals.update({
                'currency_id': company_currency.id,
                'amount_currency': -amount_to_company,
            })
        
        line_ids.append((0, 0, credit_vals))
        
        # Línea 3: Comisión (si corresponde)
        if self.commission_amount > 0 and self.income_account_id:
            commission_vals = {
                'name': f'FX Commission: {self.commission_amount}',
                'account_id': self.income_account_id.id,
                'partner_id': self.partner_id.id,
                'debit': 0.0,
                'credit': self.commission_amount,
                'currency_id': company_currency.id,
                'amount_currency': -self.commission_amount,
            }
            line_ids.append((0, 0, commission_vals))
            
            # Ajustar débito por comisión
            line_ids[0] = (0, 0, {
                **debit_vals,
                'debit': amount_from_company + self.commission_amount,
                'amount_currency': debit_vals['amount_currency'] + (
                    self.commission_amount if self.currency_from == company_currency else 0
                )
            })
        
        # Crear el asiento contable
        move_vals = {
            'ref': self.name,
            'date': self.date,
            'journal_id': self.journal_id.id,
            'partner_id': self.partner_id.id,
            'currency_id': company_currency.id,
            'move_type': 'entry',
            'line_ids': line_ids,
        }
        
        # Crear el asiento
        move = self.env['account.move'].create(move_vals)
        return move
    
    def _set_default_accounts(self):
        """Configurar cuentas por defecto basadas en configuración"""
        if not self.account_from_id:
            default_account = self.env['ir.config_parameter'].sudo().get_param('fx_exchange.inventory_account_id')
            if default_account:
                self.account_from_id = int(default_account)
        
        if not self.account_to_id:
            default_account = self.env['ir.config_parameter'].sudo().get_param('fx_exchange.inventory_account_id')
            if default_account:
                self.account_to_id = int(default_account)
        
        if not self.income_account_id:
            default_account = self.env['ir.config_parameter'].sudo().get_param('fx_exchange.income_account_id')
            if default_account:
                self.income_account_id = int(default_account)
    
    # ==================== MÉTODOS AUXILIARES ====================
    
    def _create_contact_activity(self):
        """Crear actividad para el contacto cuando se completa la operación"""
        for record in self:
            if record.partner_id:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'FX Operation Completed: {record.name}',
                    'note': f'Foreign exchange operation {record.name} has been completed.\n'
                           f'Amount: {record.amount_from} {record.currency_from.name} → '
                           f'{record.amount_to} {record.currency_to.name}\n'
                           f'Exchange Rate: {record.exchange_rate}\n'
                           f'Journal Entry: {record.move_id.name if record.move_id else "N/A"}',
                    'res_id': record.partner_id.id,
                    'res_model_id': self.env.ref('base.model_res_partner').id,
                    'user_id': self.env.user.id,
                })
    
    def action_view_contact(self):
        """Acción para ver el contacto asociado"""
        self.ensure_one()
        if not self.partner_id:
            raise UserError("No hay contacto asociado a esta operación.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contact',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_journal_entry(self):
        """Acción para ver el asiento contable"""
        self.ensure_one()
        if not self.move_id:
            raise UserError("No hay asiento contable asociado a esta operación.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
