from odoo import fields, models


class PurchasesServiceCategory(models.Model):
    _name = 'purchases.service_category'
    _inherit = ['navigation.mixin']
    _description = 'Purchases Service Category'
    _menu_code = 'service_categories'
    _rec_name = 'category_name'
    _order = 'category_name, id'

    category_name = fields.Char(string='Category Name', required=True)
    is_edit = fields.Boolean(default=False)
