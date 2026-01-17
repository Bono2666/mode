{
    'name': "Disable Autosave by Bonoworx",
    'summary': "This module disables the auto save feature of Odoo",
    'description': "This module disables the auto save feature of Odoo",

    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",

    'category': 'Technical',
    'version': '0.1',

    'depends': ['base'],

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
            'disable_autosave/static/src/css/disable_autosave.css',
        ],
    },

    'license': 'LGPL-3',
}
