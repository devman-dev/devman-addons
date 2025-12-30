{
    'name': 'Website Product Iframe',
    'version': '1.0.0',
    'summary': 'Muestra un iframe con datos del producto en el eCommerce',
    'category': 'Website',
    'depends': ['website', 'website_sale', 'casino_online','casino_online_back'],
    'data': [
        'views/website_sale_templates.xml'
    ],
    'assets': {
        'web.assets_frontend': [
            'website_product_iframe/static/src/js/product_iframe.js',
        ],
    },
    'installable': True,
    'application': False,
}