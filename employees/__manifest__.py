{
    'name': "Employees by Bonoworx",

    'summary': "Centralize employee information",

    'description': """
Centralize employee information
    """,

    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'general', 'disable_autosave'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # 'data/menu.xml',
        'views/views.xml',
        'views/templates.xml',
        'data/sequence.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3'
}
