{
    'name': "Disable Autosave by KSI",
    'summary': "This module disables the auto save feature of Odoo",
    'description': "This module disables the auto save feature of Odoo",

    'author': "KSI solusi",
    'website': "https://www.ksisolusi.com",

    'category': 'Technical',
    'version': '0.1',

    'depends': ['web'],

    'data': [
        'security/ir.model.access.csv',
        'data/prevent_model_demo.xml',
        'views/views.xml',
        'views/templates.xml',
    ],

    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'disable_autosave/static/src/js/disable_autosave.js',
        ],
    },
    'license': 'LGPL-3',
}
