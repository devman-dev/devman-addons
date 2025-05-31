# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

{
    'name': 'Material Requisition for Equipment Maintenance Request | Purchase Requisition from Maintenance Request',
    'version': '18.0.1.0',
    'sequence': 1,
    'category': 'Maintenance',
    'description':
        """
        Material Requisition for Equipment Maintenance Request, Purchase Requisition from Maintenance Request
        
 Odoo maintenance purchase agreement
Maintenance agreement management in Odoo
Odoo purchase agreement for maintenance services
Efficient maintenance purchase agreement in Odoo
Odoo maintenance contract module
Streamlined maintenance operations in Odoo
Odoo purchase agreement tracking and management
Automated maintenance purchase agreement in Odoo
Odoo maintenance purchase agreement module
Odoo contract management for maintenance
Maintenance purchase agreement in Odoo
Odoo maintenance contract management
Odoo maintenance agreement tracking
Odoo purchase agreement for equipment maintenance
Odoo maintenance agreement lifecycle management      
Odoo material requisition for equipment maintenance
Equipment maintenance material requisition in Odoo
Odoo material request for equipment maintenance
Efficient material requisition in Odoo for equipment maintenance
Odoo equipment maintenance requisition module
Streamlined equipment maintenance operations in Odoo
Odoo material requisition tracking and management
Automated material requisition for equipment maintenance in Odoo
Odoo material requisition module for equipment maintenance
Odoo equipment maintenance material request
Material requisition for equipment maintenance in Odoo
Odoo equipment maintenance material requisition management
Odoo equipment maintenance material request tracking
Odoo material requisition for equipment maintenance request
Odoo equipment maintenance material requisition lifecycle

odoo app manage material requisition from equipment maintenance, Material plan from equipment,material requisition from maintence, purchase requisition from maintence, Purchase equipment maintenance, Purchase agreement from equipment maintenance, Purchase Plan  equipment maintenance

    """,
    'summary': 'odoo app manage material requisition from equipment maintenance Material plan from equipment material requisition from maintence purchase requisition from maintence Purchase equipment maintenance Purchase agreement from equipment maintenance Purchase Plan  equipment maintenance',
    'depends': ['maintenance', 'purchase_requisition'],
    'data': [
        'security/ir.model.access.csv',
        'views/equipment.xml',
        'views/maintenance_request.xml',
        'views/agreement.xml',
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    
    # author and support Details =============#
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'https://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':12.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
    'pre_init_hook' :'pre_init_check',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
