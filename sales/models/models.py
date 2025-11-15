from odoo import models, fields, api


class cust_category(models.Model):
    _name = 'sales.cust_category'
    _description = 'sales.cust_category'

    categoryid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.cust_category'), string="Category ID")
    categorynm = fields.Char(string="Category Name")


class cust_type(models.Model):
    _name = 'sales.cust_type'
    _description = 'sales.cust_type'

    typeid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.cust_type'), string="Type ID")
    typenm = fields.Char(string="Type Name")


class cust_area(models.Model):
    _name = 'sales.cust_area'
    _description = 'sales.cust_area'

    areaid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.cust_area'), string="Area ID")
    areanm = fields.Char(string="Area Name")


class products(models.Model):
    _name = 'sales.products'
    _description = 'sales.products'

    productid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.products'), string="Product ID")
    productnm = fields.Char(string="Product Name")


class price_condition(models.Model):
    _name = 'sales.price_condition'
    _description = 'sales.price_condition'

    conditionid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.price_condition'), string="Condition ID")
    conditionnm = fields.Char(string="Condition Name")


class price_condition_detail(models.Model):
    _name = 'sales.price_condition_detail'
    _description = 'sales.price_condition_detail'

    condition_detail_id = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.price_condition_detail'), string="Condition Detail ID")
    condition_id = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='cascade', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product', ondelete='set null', index=True)
    price = fields.Float(string="Price")


class customer(models.Model):
    _name = 'sales.customer'
    _description = 'sales.customer'

    custid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.customer'), string="Customer ID")
    custnm = fields.Char(string="Customer Name")
    address = fields.Text(string="Address", size=100)
    country = fields.Many2one(
        comodel_name='general.country', string='Country', ondelete='set null', index=True)
    state = fields.Many2one(
        comodel_name='general.state', string='State', ondelete='set null', index=True)
    city = fields.Many2one(
        comodel_name='general.city', string='City', ondelete='set null', index=True)
    region = fields.Many2one(
        comodel_name='general.region', string='Region', ondelete='set null', index=True)
    salescode = fields.Many2one(
        comodel_name='employees.employees', string='Sales', ondelete='set null', index=True,
        domain=[('salescode', '!=', False)])
    npwp = fields.Char(string="NPWP")
    cust_category = fields.Many2one(
        comodel_name='sales.cust_category', string='Customer Category', ondelete='set null', index=True)
    cust_type = fields.Many2one(
        comodel_name='sales.cust_type', string='Customer Type', ondelete='set null', index=True)
    cust_area = fields.Many2one(
        comodel_name='sales.cust_area', string='Customer Area', ondelete='set null', index=True)
    price_condition = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='set null', index=True)
    contactname = fields.Char(string="Contact Name")
    telephone = fields.Char(string="Telephone")
    email = fields.Char(string="Email")
    website = fields.Char(string="Website")


class ship_to(models.Model):
    _name = 'sales.ship_to'
    _description = 'sales.ship_to'

    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', ondelete='cascade', index=True)
    ship_id = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'sales.ship_to'), string="Ship ID")
    ship_name = fields.Char(string="Ship Name")
    address = fields.Text(string="Address", size=100)
    country = fields.Many2one(
        comodel_name='general.country', string='Country', ondelete='set null', index=True)
    state = fields.Many2one(
        comodel_name='general.state', string='State', ondelete='set null', index=True)
    city = fields.Many2one(
        comodel_name='general.city', string='City', ondelete='set null', index=True)
    region = fields.Many2one(
        comodel_name='general.region', string='Region', ondelete='set null', index=True)
