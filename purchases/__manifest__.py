{
    'name': "Purchases by Bonoworx",

    'summary': "From purchase orders to vendor bills",

    'description': """
From purchase orders to vendor bills
    """,

    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",

    'category': 'Purchase',
    'version': '0.1',

    'depends': ['base', 'general', 'sales', 'employees', 'disable_autosave', 'mail'],

    'data': [
        'security/ir.model.access.csv',
        'data/menu.xml',
        'views/templates.xml',
        'views/views.xml',
        'data/sequence.xml',
        'data/mail_template_po.xml',
        'data/mail_template_approval.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'purchases/static/src/xml/based_on_so_field.xml',
            'purchases/static/src/js/based_on_so_field.js',
        ],
    },
    'license': 'LGPL-3'
}
