{
    'name': "AutoSave by KSI",

    'summary': "This module allows the user to disable the auto save feature of Odoo",

    'description': """
This module allows the user to disable the auto save feature of Odoo
    """,

    'author': "KSI Solusi",
    'website': "https://www.ksisolusi.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Technical',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/prevent_model_demo.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        "web.assets_backend": [
            "autosave/static/src/js/prevent_autosave_formcontroller.js",
            "autosave/static/src/js/prevent_autosave_listcontroller.js",
        ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
}
