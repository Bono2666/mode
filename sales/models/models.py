from odoo import models, fields, api


class NavigationMixin(models.AbstractModel):
    _name = 'navigation.mixin'
    _description = 'Mixin for General Navigation'

    model_description = fields.Char(compute='_compute_model_description')
    user_can_read = fields.Boolean(compute='_compute_custom_permissions')
    user_can_create = fields.Boolean(
        compute='_compute_custom_permissions', store=False)
    user_can_update = fields.Boolean(compute='_compute_custom_permissions')
    user_can_delete = fields.Boolean(compute='_compute_custom_permissions')

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)

        # Pengecekan Admin
        if not self.env.user.has_group('base.group_system'):
            # Cari akses di tabel kustom
            access = self.env['general.auth'].sudo().search([
                ('custom_user_id.user_id', '=', self.env.uid),
                ('menu_id.menu_id', '=', self._menu_code)
            ], limit=1)

            # Jika tidak punya akses create, hapus kemampuan create dari arsitektur view
            if not access or not access.can_create:
                for view_type in ['list', 'form']:
                    if view_type in res['views']:
                        import lxml.etree as etree
                        doc = etree.fromstring(res['views'][view_type]['arch'])
                        doc.set('create', '0')  # Paksa tombol New jadi hilang
                        res['views'][view_type]['arch'] = etree.tostring(
                            doc, encoding='unicode')
        return res

    @api.depends_context('uid')
    def _compute_custom_permissions(self):
        is_admin = self.env.user.has_group('base.group_system')

        # 2. Jika Admin, berikan akses penuh secara otomatis
        if is_admin:
            for record in self:
                record.user_can_read = True
                record.user_can_create = True
                record.user_can_update = True
                record.user_can_delete = True
            return

        menu_code = getattr(self, '_menu_code', False)

        access = self.env['general.auth'].sudo().search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', menu_code)
        ], limit=1)

        for record in self:
            if access:
                record.user_can_read = True
                record.user_can_create = access.can_create
                record.user_can_update = access.can_update
                record.user_can_delete = access.can_delete
            else:
                record.user_can_read = False
                record.user_can_create = False
                record.user_can_update = False
                record.user_can_delete = False

    def _compute_model_description(self):
        for record in self:
            record.model_description = self._description

    def action_back(self):
        self.ensure_one()
        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'context': self.env.context,
        }

    def action_edit(self):
        self.ensure_one()
        self.write({'is_edit': True})

        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', self._name),
            ('type', '=', 'form')
        ], limit=1).id

        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(view_id, 'form')],
            'target': 'current',
        }

    def action_save(self):
        self.ensure_one()
        self.write({'is_edit': False})

        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', self._name),
            ('type', '=', 'form')
        ], limit=1).id

        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(view_id, 'form')],
            'target': 'current',
        }

    def action_delete(self):
        self.ensure_one()
        self.unlink()

        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'context': self.env.context,
        }


class cust_category(models.Model):
    _name = 'sales.cust_category'
    _inherit = ['navigation.mixin']
    _description = 'Customer Category'
    _rec_name = 'category_name'
    _menu_code = 'cust_category'

    category_id = fields.Char(string="Category ID", readonly=True)
    category_name = fields.Char(string="Category Name")
    is_edit = fields.Boolean(default=False)

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
    _inherit = ['navigation.mixin']
    _description = 'Customer Type'
    _rec_name = 'type_name'
    _menu_code = 'cust_type'

    type_id = fields.Char(string="Type ID", readonly=True)
    type_name = fields.Char(string="Type Name")
    is_edit = fields.Boolean(default=False)

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
    _inherit = ['navigation.mixin']
    _description = 'Customer Area'
    _rec_name = 'area_name'
    _menu_code = 'cust_area'

    area_id = fields.Char(string="Area ID", readonly=True)
    area_name = fields.Char(string="Area Name")
    is_edit = fields.Boolean(default=False)

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
    _inherit = ['navigation.mixin']
    _description = 'Customer'
    _rec_name = 'customer_name'
    _menu_code = 'customer'

    customer_id = fields.Char(string="Customer ID", readonly=True)
    customer_name = fields.Char(string="Customer Name")
    address = fields.Text(string="Address")
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
        domain=[('sales_code', '!=', False)])
    npwp = fields.Char(string="NPWP")
    cust_category = fields.Many2one(
        comodel_name='sales.cust_category', string='Customer Category', ondelete='set null', index=True)
    cust_type = fields.Many2one(
        comodel_name='sales.cust_type', string='Customer Type', ondelete='set null', index=True)
    cust_area = fields.Many2one(
        comodel_name='sales.cust_area', string='Customer Area', ondelete='set null', index=True)
    price_condition = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='set null', index=True)
    payment_terms = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms', ondelete='set null', index=True)
    contact_name = fields.Char(string="Contact Name")
    telephone = fields.Char(string="Telephone")
    email = fields.Char(string="Email")
    website = fields.Char(string="Website")
    ship_to_ids = fields.One2many(
        'sales.ship_to', 'customer_id', string="Ship To Addresses")
    is_edit = fields.Boolean(default=False)

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
    _description = 'Ship To'
    _rec_name = 'ship_name'

    ship_id = fields.Char(string="Ship ID", readonly=True)
    ship_name = fields.Char(string="Ship Name")
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', ondelete='cascade', index=True)
    address = fields.Text(string="Address")
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


class product_type(models.Model):
    _name = 'sales.product_type'
    _inherit = ['navigation.mixin']
    _description = 'Product Type'
    _menu_code = 'product_type'

    name = fields.Char(string='Product Type')
    is_edit = fields.Boolean(default=False)


class product_unit(models.Model):
    _name = 'sales.product_unit'
    _inherit = ['navigation.mixin']
    _description = 'Product Unit'
    _rec_name = 'uom'
    _menu_code = 'product_unit'

    uom = fields.Char(string='Unit of Measure')
    qty = fields.Integer(string='Qty', default=1)
    base_uom = fields.Char(string='Base UoM')
    base_qty = fields.Integer(string='Base Qty', default=1)
    is_edit = fields.Boolean(default=False)


class products(models.Model):
    _name = 'sales.products'
    _inherit = ['navigation.mixin']
    _description = 'Products'
    _rec_name = 'product_name'
    _menu_code = 'products'

    product_id = fields.Char(string="Product ID", readonly=True)
    product_name = fields.Char(string="Product Name")
    product_type = fields.Many2one(
        comodel_name='sales.product_type', string='Product Type')
    product_unit = fields.Many2one(
        comodel_name='sales.product_unit', string='Product Unit')
    image = fields.Binary(string="Image")
    is_edit = fields.Boolean(default=False)

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
    _inherit = ['navigation.mixin']
    _description = 'Price Condition'
    _rec_name = 'price_name'
    _menu_code = 'price_condition'

    price_id = fields.Char(string="Price ID", readonly=True)
    price_name = fields.Char(string="Price Name")
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")
    product_ids = fields.One2many(
        'sales.price_condition_product', 'price_id', string="Products")
    customer_ids = fields.One2many(
        'sales.price_condition_customer', 'price_id', string="Customers")
    is_edit = fields.Boolean(default=False)

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
    _description = 'Price Condition - Product'

    price_id = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='cascade', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product', ondelete='set null', index=True)
    price = fields.Float(string="Price")


class price_condition_customer(models.Model):
    _name = 'sales.price_condition_customer'
    _description = 'Price Condition - Customer'

    price_id = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='cascade', index=True)
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', ondelete='set null', index=True)


class account_type(models.Model):
    _name = 'sales.account_type'
    _inherit = ['navigation.mixin']
    _description = 'Account Type'

    name = fields.Char(string='Account Type', required=True)
    is_edit = fields.Boolean(default=False)


class payment_terms(models.Model):
    _name = 'sales.payment_terms'
    _inherit = ['navigation.mixin']
    _description = 'Payment Terms'
    _rec_name = 'sales_text'
    _menu_code = 'payment_terms'

    payment_terms_id = fields.Char(string="Payment Terms ID", readonly=True)
    sales_text = fields.Char(string="Sales Text")
    account_type = fields.Many2many(
        'sales.account_type', string="Account Type")
    baseline_date = fields.Selection([
        ('doc', 'Document Date'),
        ('post', 'Posting Date'),
        ('entry', 'Entry Date')
    ], string="Default for Baseline Date")
    payment_terms_ids = fields.One2many(
        'sales.payment_terms_detail', 'payment_terms_id', string="Payment Terms")
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('payment_terms_id'):
                    v['payment_terms_id'] = self.env['ir.sequence'].next_by_code(
                        'sales.payment_terms') or '/'
            return super(payment_terms, self).create(vals)
        if not vals.get('payment_terms_id'):
            vals['payment_terms_id'] = self.env['ir.sequence'].next_by_code(
                'sales.payment_terms') or '/'
        return super(payment_terms, self).create(vals)


class payment_terms_detail(models.Model):
    _name = 'sales.payment_terms_detail'
    _description = 'Payment Terms - Detail'

    payment_terms_id = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms ID', ondelete='cascade', index=True)
    percentage = fields.Float(string="Percentage")
    no_of_days = fields.Integer(string="No of Days")
    explanation = fields.Char(string="Explanation")
