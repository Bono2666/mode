{
    'name': "Assets by Bonoworx",
    'summary': "Fixed Asset & Depreciation Management",
    'description': """
Track fixed assets, compute depreciation automatically,
post journal entries, dispose and revalue assets.
Supports Straight Line, Declining Balance,
and Declining then Straight Line methods.
    """,
    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",
    'category': 'Accounting',
    'version': '0.1',
    'depends': ['base', 'general', 'accounting', 'purchases', 'employees', 'disable_autosave'],
    'data': [
        'security/ir.model.access.csv',
        'data/menu.xml',
        'data/sequence.xml',
        'data/chart_of_accounts_additions.xml',
        'data/cron.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    'demo': ['demo/demo.xml'],
    'license': 'LGPL-3',
}
