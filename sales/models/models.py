from odoo import models, fields, api


class cust_category(models.Model):
    _name = 'sales.cust_category'
    _description = 'sales.cust_category'

    category_id = fields.Char(string="Category ID",
                              primary_key=True, readonly=True)
    category_name = fields.Char(string="Category Name")

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('category_id'):
                    v['category_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.cust_category') or '/'
            return super(cust_category, self).create(vals)
        if not vals.get('category_id'):
            vals['category_id'] = self.env['ir.sequence'].next_by_code(
                'sales.cust_category') or '/'
        return super(cust_category, self).create(vals)


class cust_type(models.Model):
    _name = 'sales.cust_type'
    _description = 'sales.cust_type'

    type_id = fields.Char(string="Type ID", primary_key=True, readonly=True)
    type_name = fields.Char(string="Type Name")

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('type_id'):
                    v['type_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.cust_type') or '/'
            return super(cust_type, self).create(vals)
        if not vals.get('type_id'):
            vals['type_id'] = self.env['ir.sequence'].next_by_code(
                'sales.cust_type') or '/'
        return super(cust_type, self).create(vals)


class cust_area(models.Model):
    _name = 'sales.cust_area'
    _description = 'sales.cust_area'

    area_id = fields.Char(string="Area ID", primary_key=True, readonly=True)
    area_name = fields.Char(string="Area Name")

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('area_id'):
                    v['area_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.cust_area') or '/'
            return super(cust_area, self).create(vals)
        if not vals.get('area_id'):
            vals['area_id'] = self.env['ir.sequence'].next_by_code(
                'sales.cust_area') or '/'
        return super(cust_area, self).create(vals)


class customer(models.Model):
    _name = 'sales.customer'
    _description = 'sales.customer'

    customer_id = fields.Char(string="Customer ID",
                              primary_key=True, readonly=True)
    customer_name = fields.Char(string="Customer Name")
    address = fields.Text(string="Address", size=100)
    country = fields.Many2one(
        comodel_name='general.country', string='Country', ondelete='set null', index=True)
    state = fields.Many2one(
        comodel_name='general.state', string='State', ondelete='set null', index=True)
    city = fields.Many2one(
        comodel_name='general.city', string='City', ondelete='set null', index=True)
    district = fields.Many2one(
        comodel_name='general.district', string='District', ondelete='set null', index=True)
    sales_code = fields.Many2one(
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

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('customer_id'):
                    v['customer_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.customer') or '/'
            return super(customer, self).create(vals)
        if not vals.get('customer_id'):
            vals['customer_id'] = self.env['ir.sequence'].next_by_code(
                'sales.customer') or '/'
        return super(customer, self).create(vals)


class ship_to(models.Model):
    _name = 'sales.ship_to'
    _description = 'sales.ship_to'

    ship_id = fields.Char(string="Ship ID", primary_key=True, readonly=True)
    ship_name = fields.Char(string="Ship Name")
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', ondelete='cascade', index=True)
    address = fields.Text(string="Address", size=100)
    country = fields.Many2one(
        comodel_name='general.country', string='Country', ondelete='set null', index=True)
    state = fields.Many2one(
        comodel_name='general.state', string='State', ondelete='set null', index=True)
    city = fields.Many2one(
        comodel_name='general.city', string='City', ondelete='set null', index=True)
    district = fields.Many2one(
        comodel_name='general.district', string='District', ondelete='set null', index=True)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('ship_id'):
                    v['ship_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.ship_to') or '/'
            return super(ship_to, self).create(vals)
        if not vals.get('ship_id'):
            vals['ship_id'] = self.env['ir.sequence'].next_by_code(
                'sales.ship_to') or '/'
        return super(ship_to, self).create(vals)


class products(models.Model):
    _name = 'sales.products'
    _description = 'sales.products'

    product_id = fields.Char(
        string="Product ID", primary_key=True, readonly=True)
    product_name = fields.Char(string="Product Name")
    image = fields.Binary(string="Image")

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('product_id'):
                    v['product_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.products') or '/'
            return super(products, self).create(vals)
        if not vals.get('product_id'):
            vals['product_id'] = self.env['ir.sequence'].next_by_code(
                'sales.products') or '/'
        return super(products, self).create(vals)


class price_condition(models.Model):
    _name = 'sales.price_condition'
    _description = 'sales.price_condition'

    price_id = fields.Char(
        string="Price ID", primary_key=True, readonly=True)
    price_name = fields.Char(string="Price Name")
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('price_id'):
                    v['price_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.price_condition') or '/'
            return super(price_condition, self).create(vals)
        if not vals.get('price_id'):
            vals['price_id'] = self.env['ir.sequence'].next_by_code(
                'sales.price_condition') or '/'
        return super(price_condition, self).create(vals)


class price_condition_product(models.Model):
    _name = 'sales.price_condition_product'
    _description = 'sales.price_condition_product'

    condition_id = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='cascade', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product', ondelete='set null', index=True)
    price = fields.Float(string="Price")


class price_condition_customer(models.Model):
    _name = 'sales.price_condition_customer'
    _description = 'sales.price_condition_customer'

    condition_id = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='cascade', index=True)
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', ondelete='set null', index=True)
