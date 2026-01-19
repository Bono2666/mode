{
    'name': "General by Bonoworx",

    'summary': "General Master Table",

    'description': """
General Master Table
    """,

    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Technical',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'disable_autosave'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'data/menu.xml',
        'data/home.xml',
        'views/views.xml',
        'data/sequence.xml',
        'data/logo.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'general/static/src/js/navbar.xml',
        ],
    },

    'license': 'LGPL-3',
}
