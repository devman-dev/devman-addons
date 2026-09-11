# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Safa KB @ Cybrosys, (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
"""
DEPRECATED — signup.approval (legacy model)

This model is replaced by res.users.approve, which now includes full
casino player integration (wallet, agent, welcome bonus).

DO NOT USE this model for new signup approvals.
Existing records are preserved for data integrity.

Migration: new signups go through res.users.approve.
"""

from odoo import fields, models


class SignupApproval(models.Model):
    """DEPRECATED — Legacy signup approval.

    Replaced by res.users.approve with casino player integration.
    This model only exists to preserve existing data.
    """
    _name = 'signup.approval'
    _description = "DEPRECATED — Signup Approval (legacy)"

    partner_id = fields.Many2one(
        'res.partner',
        string="Partner",
        help="Partner for the signup request",
    )
    name = fields.Char(
        string='User Name',
        help="Name of the user",
    )
    email = fields.Char(
        string='User Email',
        help="Email of the user",
    )
    message = fields.Char(
        string='Message',
        help="Message from the user",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help="Company to signup to",
    )
    phone = fields.Char(
        string='Phone',
        help="Phone number of the user",
    )
    sale_team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        help="Sales team for the signup request",
    )
    state = fields.Selection(
        [
            ('draft', 'New'),
            ('confirm', 'Waiting Approval'),
            ('done', 'Approved'),
            ('refuse', 'Refused'),
        ],
        string='State',
        default='draft',
        help="Status of the signup request",
    )

    # Prevent creation of new records in this legacy model
    active = fields.Boolean(default=True)