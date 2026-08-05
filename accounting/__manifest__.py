{
    'name': "Accounting by Bonoworx",
    'summary': "Chart of Accounts, Journal Entries, Financial Reports",
    'description': """
Complete custom accounting module with Chart of Accounts,
double-entry journal entries, period management,
financial reports, and full integration with Sales Invoices,
Sales Payments, and Vendor Bills.
    """,
    'author': "Bonoworx",
    'website': "https://www.bonoworx.com",
    'category': 'Accounting',
    'version': '0.1',
    'depends': ['base', 'general', 'disable_autosave', 'sales', 'purchases'],
    'post_init_hook': 'post_init_hook',
    'data': [
        'security/ir.model.access.csv',
        'data/account_type.xml',
        'data/chart_of_accounts.xml',
        'data/journal_data.xml',
        'data/fiscal_year.xml',
        'data/tax_data.xml',
        'data/sequence.xml',
        'data/menu.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3',
}
