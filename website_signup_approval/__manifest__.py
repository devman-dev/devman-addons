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
{
    'name': "Website Signup Approval + Casino Integration",
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': """Website Signup Approval with Casino Player Integration""",
    'description': """Control user signups by requiring admin approval,
with full casino player integration (wallet creation, agent assignment,
welcome bonus via casino.money.flow).""",
    'author': 'Cybrosys Techno Solutions, Adapted by Hitofusion',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': ['website', 'website_sale', 'casino_online_back', 'auth_signup'],
    'data': [
        'security/website_signup_approval_groups.xml',
        'security/ir.model.access.csv',
        'data/website_signup_approval_data.xml',
        'views/approval_request_templates.xml',
        'views/res_users_approve_views.xml',
        'views/res_config_settings_views.xml',
        'views/document_attachment_views.xml',
        'views/signup_templates.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}