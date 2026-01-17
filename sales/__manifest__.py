{
    'name': "Sales by Bonoworx",

    'summary': "From quotations to invoices",

    'description': """
From quotations to invoices
    """,

    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'general', 'employees', 'disable_autosave'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/views.xml',
        'data/sequence.xml',
        'data/account_type.xml',
        'data/product_type.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3'
}
