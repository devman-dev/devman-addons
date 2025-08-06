{
    'name': 'Casino Online',
    'category': 'Website/eCommerce',
    'summary': 'Online casino platform with eCommerce integration',
    'version': '1.0.0',
    'license': 'LGPL-3',
    'author': 'Gerlin Matos',
    'website': 'https://github.com/gerlinmatos',
    'description': """
        Casino Online Module
        ===================
        
        This module provides a complete online casino platform integrated with Odoo's eCommerce system.
        
        Features:
        - Casino game integration with eCommerce portal
        - Custom portal templates for casino users
        - Payment processing for gaming transactions
        - User account management for casino players
        - Secure gaming environment with account integration
        
        This module extends the standard eCommerce functionality to support online casino operations
        while maintaining compatibility with Odoo's portal and payment systems.
    """,
    'images': ['static/description/icon.png'],
    'depends': ['website_sale', 'portal', 'account', 'payment'],
    'data': [
        'security/ir.model.access.csv',
        'views/templates/strip_template.xml',
        'views/templates/user_options_template.xml',
        'views/templates/transactions_template.xml'
    ],
    'installable': True,
}
