# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Configuración de límites de apuesta
    bet_msg_daily   = fields.Char(string="Mensaje límite diario",   default="")
    bet_msg_weekly  = fields.Char(string="Mensaje límite semanal",  default="")
    bet_msg_monthly = fields.Char(string="Mensaje límite mensual",  default="")

    # Configuración de diarios bancarios para casino
    casino_deposit_journal_id = fields.Many2one(
        'account.journal',
        string='Diario para Depósitos de Casino',
        help='Diario contable utilizado para registrar los depósitos de los usuarios del casino',
        domain=[('type', 'in', ['bank', 'cash'])]
    )
    
    casino_bet_transfer_journal_id = fields.Many2one(
        'account.journal',
        string='Diario para Transferencias de Apuestas',
        help='Diario contable utilizado para registrar las transferencias de apuestas/pérdidas del casino',
        domain=[('type', 'in', ['general'])]
    )
    
    # Configuración de cuentas contables para casino
    casino_deposit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta para Depósitos de Casino',
        help='Cuenta contable específica para depósitos de casino. Si no se especifica, se usará la cuenta por defecto del diario.',
        domain=[('deprecated', '=', False)]
    )
    
    casino_bet_account_id = fields.Many2one(
        'account.account',
        string='Cuenta para Apuestas de Casino',
        help='Cuenta contable específica para apuestas/pérdidas de casino. Si no se especifica, se usará la cuenta por defecto del diario.',
        domain=[('deprecated', '=', False)]
    )