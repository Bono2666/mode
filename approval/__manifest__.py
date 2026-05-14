{
    'name': "Approval by Bonoworx",

    'summary': "Approval management for business processes",

    'description': """
Approval management for business processes
    """,

    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",

    'category': 'Technical',
    'version': '0.1',

    'depends': ['base', 'general', 'disable_autosave', 'mail'],

    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/views.xml',
        'data/menu.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3'
}
