from datetime import timedelta
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


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

    def action_back_kanban(self):
        self.ensure_one()
        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'kanban,form',
            'views': [(False, 'kanban'), (False, 'form')],
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
    _description = 'Customer Categories'
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

    def unlink(self):
        for record in self:
            # Check if there are any customers using this category
            customer_count = self.env['sales.customer'].search_count([
                ('cust_category', '=', record.id)
            ])

            if customer_count > 0:
                raise UserError(_(
                    "The category '%s' cannot be deleted because it is still assigned to %s customer(s). "
                    "Please reassign these customers to another category before deleting."
                ) % (record.category_name, customer_count))

        return super(cust_category, self).unlink()


class cust_type(models.Model):
    _name = 'sales.cust_type'
    _inherit = ['navigation.mixin']
    _description = 'Customer Types'
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
    _description = 'Customer Areas'
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


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    customer_ids = fields.Many2many(
        'sales.customer',
        string='Customers',
        context={'show_email_in_wizard': True},
        help="Select customers to add as recipients"
    )

    @api.onchange('customer_ids')
    def _onchange_customer_ids(self):
        """ Automatically sync selected customers to the actual recipients field """
        if self.customer_ids:
            # Map the selected custom customers back to their res.partner IDs
            partner_ids = self.customer_ids.mapped('partner_id.id')
            # Add them to the standard field so Odoo knows who to email
            self.partner_ids = [(6, 0, partner_ids)]

    def send_mail(self, auto_commit=False):
        res = super().send_mail(auto_commit=auto_commit)
        redirect_action = self.env.context.get('redirect_to_tree')
        if redirect_action:
            try:
                action = self.env.ref(redirect_action).sudo().read()[0]
                action['target'] = 'main'
                return action
            except Exception:
                pass
        return res


class customer(models.Model):
    _name = 'sales.customer'
    _inherit = ['navigation.mixin']
    _description = 'Customers'
    _rec_name = 'customer_name'
    _menu_code = 'customers'

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
    postal_code = fields.Char(string="Postal Code")
    sales_name = fields.Many2one(
        comodel_name='general.custom_users', string='Salesperson', ondelete='set null', index=True, domain=[('menu_ids.menu_id', 'in', ['Sales Orders', 'Quotations', 'Customers'])])
    npwp = fields.Char(string="NPWP")
    cust_category = fields.Many2one(
        comodel_name='sales.cust_category', string='Customer Category', index=True, required=True, ondelete='cascade')
    cust_type = fields.Many2one(
        comodel_name='sales.cust_type', string='Customer Type', ondelete='set null', index=True)
    cust_area = fields.Many2one(
        comodel_name='sales.cust_area', string='Customer Area', ondelete='set null', index=True)
    price_condition_ids = fields.Many2many(
        'sales.price_condition',
        'customer_price_condition_rel',  # Table name
        'customer_id',
        'price_id',
        string="Price Conditions"
    )
    payment_terms = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms', ondelete='set null', index=True, domain="[('account_type', '=', 'Customer')]")
    contact_name = fields.Char(string="Contact Name")
    telephone = fields.Char(string="Telephone")
    email = fields.Char(string="Email", required=True)
    website = fields.Char(string="Website")
    ship_to_ids = fields.One2many(
        'sales.ship_to', 'customer_id', string="Ship To Addresses")
    is_edit = fields.Boolean(default=False)
    partner_id = fields.Many2one(
        'res.partner', string="Related Partner", ondelete='cascade')
    image_1920 = fields.Binary(string="Image 1920")
    avatar_128 = fields.Binary(
        string="Avatar 128", related='partner_id.avatar_128')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('customer_id'):
                vals['customer_id'] = self.env['ir.sequence'].next_by_code(
                    'sales.customer') or '/'

            # --- CREATE PARTNER ---
            partner = self.env['res.partner'].sudo().create({
                'name': vals.get('customer_name'),
                'email': vals.get('email'),
                'phone': vals.get('telephone'),
                'website': vals.get('website'),
                'street': vals.get('address'),
                'city': vals.get('city') and self.env['general.city'].browse(vals.get('city')).city_name or '',
                'state_id': vals.get('state'),
                'country_id': vals.get('country'),
                'user_id': vals.get('sales_name'),
                'vat': vals.get('npwp'),
                'image_1920': vals.get('image_1920'),
            })
            vals['partner_id'] = partner.id

        records = super(customer, self).create(vals_list)
        for record in records:
            record._resync_price_conditions()
        return records

    def write(self, vals):
        # 1. Execute standard write
        res = super(customer, self).write(vals)

        # --- UPDATE PARTNER ---
        # Siapkan data yang akan diupdate ke partner
        partner_vals = {}
        if 'customer_name' in vals:
            partner_vals['name'] = vals['customer_name']
        if 'email' in vals:
            partner_vals['email'] = vals['email']
        if 'telephone' in vals:
            partner_vals['phone'] = vals['telephone']
        if 'address' in vals:
            partner_vals['street'] = vals['address']
        if 'city' in vals:
            partner_vals['city'] = self.env['general.city'].browse(
                vals['city']).city_name if vals['city'] else ''
        if 'state' in vals:
            partner_vals['state_id'] = vals['state']
        if 'country' in vals:
            partner_vals['country_id'] = vals['country']
        if 'sales_name' in vals:
            partner_vals['user_id'] = vals['sales_name']
        if 'npwp' in vals:
            partner_vals['vat'] = vals['npwp']
        if 'image_1920' in vals:
            partner_vals['image_1920'] = vals['image_1920']

        if partner_vals:
            for rec in self:
                if rec.partner_id:
                    rec.partner_id.sudo().write(partner_vals)

        # 2. Trigger re-sync price condition
        if 'cust_category' in vals:
            for rec in self:
                rec._resync_price_conditions()
        return res

    def unlink(self):
        # --- DELETE PARTNER ---
        # Ambil semua partner_id sebelum record sales.customer dihapus
        partners_to_delete = self.mapped('partner_id')

        # Jalankan unlink standar
        res = super(customer, self).unlink()

        # Hapus partner terkait (hanya jika masih ada)
        if partners_to_delete:
            partners_to_delete.sudo().unlink()

        return res

    def _resync_price_conditions(self):
        """Finds all applicable price conditions for this specific customer"""
        self.ensure_one()
        now = fields.Datetime.now()

        # Define the domain to find matching conditions
        domain = [
            '|', ('date_start', '=', False), ('date_start', '<=', now),
            '|', ('date_end', '=', False), ('date_end', '>=', now),
            '|',
            ('customer_applied_on', '=', 'all'),
            '|',
            '&', ('customer_applied_on', '=', 'category'),
            ('customer_category_ids', 'in', self.cust_category.ids),
            '&', ('customer_applied_on', '=', 'customer'),
            ('customer_ids.customer_id', '=', self.id)
        ]

        matching_conditions = self.env['sales.price_condition'].search(domain)

        # Command (6, 0, [IDs]) replaces the existing M2M links with the new list
        self.write({'price_condition_ids': [(6, 0, matching_conditions.ids)]})


class SalesCustomer(models.Model):
    _inherit = 'sales.customer'

    @api.depends('customer_name', 'email')
    def _compute_display_name(self):
        # Cek apakah ada instruksi khusus dari context
        show_email = self.env.context.get('show_email_in_wizard')
        for record in self:
            if show_email and record.email:
                record.display_name = f"{record.customer_name} <{record.email}>"
            else:
                record.display_name = record.customer_name


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
    postal_code = fields.Char(string="Postal Code")

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
    _description = 'Product Types'
    _menu_code = 'product_type'

    name = fields.Char(string='Product Type')
    is_edit = fields.Boolean(default=False)


class product_category(models.Model):
    _name = 'sales.product_category'
    _inherit = ['navigation.mixin']
    _description = 'Product Categories'
    _rec_name = 'category_name'
    _menu_code = 'product_category'

    category_name = fields.Char(string="Category Name")
    is_edit = fields.Boolean(default=False)

    def unlink(self):
        for record in self:
            # Check if there are any products using this category
            product_count = self.env['sales.products'].search_count([
                ('product_category', '=', record.id)
            ])

            if product_count > 0:
                raise UserError(_(
                    "The category '%s' cannot be deleted because it is still assigned to %s product(s). "
                    "Please reassign these products to another category before deleting."
                ) % (record.category_name, product_count))

        return super(product_category, self).unlink()


class product_unit(models.Model):
    _name = 'sales.product_unit'
    _inherit = ['navigation.mixin']
    _description = 'Product Units'
    _rec_name = 'uom'
    _menu_code = 'product_unit'

    uom = fields.Char(string='Unit of Measure')
    qty = fields.Integer(string='Qty', default=1)
    base_uom = fields.Char(string='Base UoM')
    base_qty = fields.Integer(string='Base Qty', default=1)
    is_edit = fields.Boolean(default=False)


# SO states that reserve stock (booking) while the order is open.
RESERVED_SO_STATES = (
    'draft', 'sale_draft', 'wait_approval', 'approved', 'sent', 'sale',
)


class products(models.Model):
    _name = 'sales.products'
    _inherit = ['navigation.mixin']
    _description = 'Products'
    _rec_name = 'product_name'
    _menu_code = 'products'

    product_id = fields.Char(string="Product ID")
    product_name = fields.Char(string="Product Name")
    sales_ok = fields.Boolean(string="Sales", default=True)
    purchase_ok = fields.Boolean(string="Purchase", default=True)
    barcode = fields.Char(string="Barcode")
    product_type = fields.Many2one(
        comodel_name='sales.product_type', string='Product Type')
    product_category = fields.Many2one(
        comodel_name='sales.product_category', string='Product Category', ondelete='cascade', index=True, required=True)
    product_unit = fields.Many2one(
        comodel_name='sales.product_unit', string='Product Unit')
    base_price = fields.Float(string="Sales Price", digits=(16, 0))
    price = fields.Float(string="Price", digits=(16, 0))
    tax_string = fields.Char(
        compute='_compute_tax_string', string='Tax Description')
    customer_tax = fields.Many2one(
        comodel_name='sales.taxes', string='Customer Tax', default=lambda self: self.env['sales.taxes'].search([('default_tax', '=', True)], limit=1))
    stock = fields.Integer(string='Stock', default=0)
    sales_order_line_ids = fields.One2many(
        'sales.sales_order_line', 'product_id', string='Sales Order Lines')
    qty_reserved_sale = fields.Integer(
        string='Booked (Open SO)', compute='_compute_qty_reserved_sale',
        store=True,
        help='Total quantity booked on open Sales Orders (not cancelled).')
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

    @api.depends('customer_tax', 'base_price')
    def _compute_tax_string(self):
        for record in self:
            if record.customer_tax:
                tax_amount = record.base_price * \
                    (record.customer_tax.tax_percentage / 100)
                total_price = record.base_price + tax_amount
                formatted_price = "{:,.0f}".format(total_price)
                record.tax_string = f"(= {formatted_price} Incl. Taxes)"
            else:
                record.tax_string = ""

    @api.depends('sales_order_line_ids.quantity', 'sales_order_line_ids.sales_order_id.state')
    def _compute_qty_reserved_sale(self):
        for product in self:
            lines = product.sales_order_line_ids.filtered(
                lambda l: l.sales_order_id
                and l.sales_order_id.state in RESERVED_SO_STATES)
            product.qty_reserved_sale = sum(lines.mapped('quantity'))

    def action_back_kanban(self):
        """Open the canonical Products action (kanban) so the Back button
        behaves the same as the main Products menu.
        """
        self.ensure_one()
        try:
            return self.env.ref('sales.products_action').sudo().read()[0]
        except Exception:
            return super(products, self).action_back_kanban()


class price_condition(models.Model):
    _name = 'sales.price_condition'
    _inherit = ['navigation.mixin']
    _description = 'Price Conditions'
    _rec_name = 'price_name'
    _menu_code = 'price_condition'
    _order = 'customer_priority asc, product_priority asc, id desc'

    price_name = fields.Char(string="Price Name")
    date_start = fields.Datetime(string="Validity")
    date_end = fields.Datetime(string="Expiry Date")
    min_quantity = fields.Integer(string="Min. Quantity", default=1)
    compute_price = fields.Selection([
        ('fixed', 'Fixed Price'),
        ('discount', 'Discount')
    ], string="Computation", default='fixed')
    fixed_price = fields.Float(string="Fixed Price", digits=(16, 0))
    percent_price = fields.Float(string="Discount")
    price = fields.Char(
        string="Price", compute='_compute_price', store=False)
    applied_on = fields.Selection([
        ('all', 'All Products'),
        ('category', 'Product Category'),
        ('product', 'Specific Products')
    ], string="Apply On", default='all')
    product_category_ids = fields.Many2many(
        'sales.product_category', string="Product Categories")
    product_ids = fields.One2many(
        'sales.price_condition_product', 'price_id', string="Products")
    product_priority = fields.Integer(
        compute="_compute_product_priority", store=True)
    customer_applied_on = fields.Selection([
        ('all', 'All Customers'),
        ('category', 'Customer Category'),
        ('customer', 'Specific Customers')
    ], string="Apply On", default='all')
    customer_category_ids = fields.Many2many(
        'sales.cust_category', string='Customer Categories')
    customer_priority = fields.Integer(
        compute="_compute_customer_priority", store=True)
    customer_ids = fields.One2many(
        'sales.price_condition_customer', 'price_id', string="Customers")
    is_edit = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(price_condition, self).create(vals_list)
        for record in records:
            record._sync_to_customers()
        return records

    def write(self, vals):
        res = super(price_condition, self).write(vals)
        # Trigger sync if rules change
        trigger_fields = ['customer_applied_on',
                          'customer_category_ids', 'customer_ids']
        if any(f in vals for f in trigger_fields):
            for record in self:
                record._sync_to_customers()
        return res

    def _sync_to_customers(self):
        """ Push this Price Condition ID to the relevant customers """
        self.ensure_one()

        # 1. REMOVE this condition from ALL customers first (as requested)
        # Using a direct SQL query is faster for mass clearing if the DB is large
        self.env.cr.execute(
            "DELETE FROM customer_price_condition_rel WHERE price_id = %s", (self.id,))
        self.invalidate_recordset()  # Clear cache after SQL

        # 2. Identify target customers
        target_customers = self.env['sales.customer']

        if self.customer_applied_on == 'all':
            target_customers = self.env['sales.customer'].search([])

        elif self.customer_applied_on == 'category' and self.customer_category_ids:
            target_customers = self.env['sales.customer'].search([
                ('cust_category', 'in', self.customer_category_ids.ids)
            ])

        elif self.customer_applied_on == 'customer':
            # Take IDs from the One2many table 'customer_ids'
            target_ids = self.customer_ids.mapped('customer_id.id')
            target_customers = self.env['sales.customer'].browse(target_ids)

        # 3. ADD this Price Condition to the found customers
        if target_customers:
            # (4, ID) is the Odoo command to add a link in Many2many without deleting existing ones
            target_customers.write({'price_condition_ids': [(4, self.id)]})

    @api.depends('compute_price', 'fixed_price', 'percent_price')
    def _compute_price(self):
        for record in self:
            if record.compute_price == 'fixed':
                record.price = f"{record.fixed_price:,.0f}"
            elif record.compute_price == 'discount':
                record.price = f"{record.percent_price:,.0f} % Discount"

    @api.depends('applied_on')
    def _compute_product_priority(self):
        for record in self:
            if record.applied_on == 'all':
                record.product_priority = 3
            elif record.applied_on == 'category':
                record.product_priority = 2
            elif record.applied_on == 'product':
                record.product_priority = 1

    @api.depends('customer_applied_on')
    def _compute_customer_priority(self):
        for record in self:
            if record.customer_applied_on == 'all':
                record.customer_priority = 3
            elif record.customer_applied_on == 'category':
                record.customer_priority = 2
            elif record.customer_applied_on == 'customer':
                record.customer_priority = 1


class price_condition_product(models.Model):
    _name = 'sales.price_condition_product'
    _description = 'Price Condition - Product'

    price_id = fields.Many2one(
        comodel_name='sales.price_condition', string='Price Condition', ondelete='cascade', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product', ondelete='set null', index=True)


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
    _description = 'Account Types'

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
    early_discount = fields.Boolean(string="Early Payment Disc.")
    discount_percentage = fields.Float(
        string="Discount Percentage", digits=(3, 0))
    discount_days = fields.Integer(string="Discount Days")
    account_type = fields.Many2many(
        'sales.account_type', string="Account Type", required=True)
    baseline_date = fields.Selection([
        ('doc', 'Document Date'),
        ('post', 'Posting Date'),
        ('entry', 'Entry Date')
    ], string="Default for Baseline Date", default='doc', required=True)
    example_amount = fields.Float(
        default=10000000, string="Example Amount", digits=(16, 0))
    example_date = fields.Date(
        string="Example Date", default=fields.Date.today())
    note = fields.Html(string="Notes")
    example_preview_discount = fields.Html(
        string="Early Payment Discount Preview", compute='_compute_example_preview', sanitize=False)
    example_preview = fields.Html(
        string="Example Preview", compute='_compute_example_preview', sanitize=False)
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

    @api.depends('example_amount', 'example_date', 'payment_terms_ids.no_of_days', 'payment_terms_ids.percentage', 'early_discount', 'discount_percentage', 'discount_days')
    def _compute_example_preview(self):
        if self.early_discount:
            discount_amount = self.example_amount - \
                (self.example_amount * (self.discount_percentage / 100))
            discount_due_date = self.example_date + \
                timedelta(days=self.discount_days)
            self.example_preview_discount = f"<div>Early Payment Discount: <b>Rp {discount_amount:,.0f}</b> if paid before <b>{discount_due_date.strftime('%m/%d/%Y')}</b></div>"
        else:
            self.example_preview_discount = "<div><b>Early Payment Discount:</b> Not Applicable</div>"

        for record in self:
            if not record.payment_terms_ids:
                record.example_preview = "No payment terms defined"
                return

            total_percentage = sum(
                record.payment_terms_ids.mapped('percentage'))
            if total_percentage > 100:
                record.example_preview = '<span style="color: red;">Total percentage exceeds 100%</span>'
                continue

            lines = []
            for i, term in enumerate(record.payment_terms_ids):
                if term.percentage > 0:
                    amount = record.example_amount * (term.percentage / 100)
                    due_date = record.example_date + \
                        timedelta(days=term.no_of_days)
                    lines.append(
                        f"<div><b>{i+1}#</b> Installment of <b>Rp {amount:,.0f}</b> due on <b style='color: #704A66;'>{due_date.strftime('%m/%d/%Y')}</b></div>")

            record.example_preview = "".join(lines)

    @api.onchange('sales_text')
    def _onchange_sales_text(self):
        if self.sales_text:
            self.note = f"<b>Payment terms:</b> {self.sales_text}"


class payment_terms_detail(models.Model):
    _name = 'sales.payment_terms_detail'
    _description = 'Payment Terms - Detail'

    payment_terms_id = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms ID', ondelete='cascade', index=True)
    percentage = fields.Float(string="Percentage")
    no_of_days = fields.Integer(string="No of Days")
    explanation = fields.Char(string="Explanation",
                              readonly=True, compute='_compute_explanation')

    @api.depends('payment_terms_id.baseline_date')
    def _compute_explanation(self):
        for record in self:
            if record.payment_terms_id.baseline_date == 'doc':
                record.explanation = "After document date"
            elif record.payment_terms_id.baseline_date == 'post':
                record.explanation = "After posting date"
            elif record.payment_terms_id.baseline_date == 'entry':
                record.explanation = "After entry date"


class discount_wizard(models.TransientModel):
    _name = 'sales.discount_wizard'
    _description = 'Discount Wizard'

    sales_order_id = fields.Many2one(
        comodel_name='sales.sales_order', string='Quotation', ondelete='cascade', index=True, readonly=True)
    discount_percentage = fields.Float(
        string="Discount", default=0, digits=(5, 0))

    def apply_discount(self):
        self.ensure_one()
        order = self.sales_order_id
        discount = self.discount_percentage

        for line in order.order_line_ids:
            line.discount = discount


class sales_order(models.Model):
    _name = 'sales.sales_order'
    _inherit = ['navigation.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Sales Orders'
    _rec_name = 'sales_code'
    _menu_code = 'sales_order'
    _order = 'sales_code desc'

    sales_code = fields.Char(string="Sales Code", readonly=True)
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', index=True, required=True)
    address = fields.Text(compute='_compute_address')
    expiry_date = fields.Date(
        string="Expiration", default=fields.Date.add(fields.Date.today(), days=10))
    quotation_date = fields.Date(
        string="Quotation Date", default=fields.Date.today())
    date_ordered = fields.Date(string="Order Date")
    payment_terms = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms', ondelete='set null', index=True, domain="[('account_type', '=', 'Customer')]")
    sales_name = fields.Many2one(
        comodel_name='general.custom_users', string='Salesperson', ondelete='set null', index=True, default=lambda self: self.env['general.custom_users'].search([('user_id', '=', self.env.uid)], limit=1), domain=[('menu_ids.menu_id', 'in', ['Sales Orders', 'Quotations'])])
    commitment_date = fields.Date(string="Delivery Date")
    expected_date = fields.Date(
        string="Expected Date", default=fields.Date.add(fields.Date.today(), days=7), readonly=True)
    order_line_ids = fields.One2many(
        'sales.sales_order_line', 'sales_order_id', string='Order Lines')
    total_amount_untaxed = fields.Float(
        string="Untaxed Total", compute='_compute_total_amount', store=True, digits=(16, 0))
    total_tax = fields.Float(
        string="Total Tax", compute='_compute_total_amount', store=True, digits=(16, 0))
    total_amount = fields.Float(
        string="Total", compute='_compute_total_amount', store=True, digits=(16, 0))
    approval_log_ids = fields.One2many(
        'sales.sales_approval_log', 'sales_order_id', string="Approval Logs")
    need_approval = fields.Boolean(compute='_compute_need_approval')
    approval_status = fields.Selection([
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Approval Status", default='pending')
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sale_draft', 'Draft'),
        ('wait_approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('cancel', 'Cancelled')
    ], string="Status", default='draft')
    invoice_status = fields.Selection([
        ('no', 'No Invoice'),
        ('to_invoice', 'To Invoice'),
        ('invoiced', 'Fully Invoiced')
    ], string="Invoicing Status", compute='_compute_invoice_status', store=True)
    invoice_ids = fields.One2many(
        'sales.invoice', 'sales_order_id', string='Invoices')
    invoice_count = fields.Integer(
        string='Invoice Count', compute='_compute_invoice_count')
    note = fields.Text(string="Terms and Conditions")
    current_approver = fields.Char(
        string="Pending Approval From", compute='_compute_current_approver', store=True)
    current_approver_name = fields.Char(
        compute='_compute_current_approver', store=True)
    is_edit = fields.Boolean(default=False)
    is_revised = fields.Boolean(default=False)
    is_quotation = fields.Boolean(default=False)
    user_can_approve = fields.Boolean(
        string="User Can Approve", compute='_compute_approval_permissions')
    user_can_revise = fields.Boolean(
        string="User Can Revise", compute='_compute_approval_permissions')
    user_can_return = fields.Boolean(
        string="User Can Return", compute='_compute_approval_permissions')
    user_can_reject = fields.Boolean(
        string="User Can Reject", compute='_compute_approval_permissions')
    user_can_submit = fields.Boolean(
        string="User Can Submit", compute='_compute_submit_permissions')
    user_can_send = fields.Boolean(
        string="User Can Send", compute='_compute_send_permissions')
    user_can_confirm = fields.Boolean(
        string="User Can Confirm", compute='_compute_confirm_permissions')
    user_can_invoicing = fields.Boolean(
        string="User Can Invoicing", compute='_compute_invoicing_permissions')

    @api.depends('customer_id.address', 'customer_id.district', 'customer_id.city', 'customer_id.state', 'customer_id.postal_code', 'customer_id.country')
    def _compute_address(self):
        for record in self:
            parts = []
            if record.customer_id.address:
                parts.append(record.customer_id.address)
            if record.customer_id.district:
                parts.append(record.customer_id.district.district_name)
            if record.customer_id.city:
                parts.append(record.customer_id.city.city_name)
            if record.customer_id.state:
                parts.append(record.customer_id.state.state_name)
            if record.customer_id.postal_code:
                parts.append(record.customer_id.postal_code)
            if record.customer_id.country:
                parts.append(record.customer_id.country.country_name)
            record.address = ', '.join(parts)

    # Override _rec_names_search to include customer contact name
    @property
    def _rec_names_search(self):
        if self._context.get('customer_id.contact_name'):
            return ['name', 'customer_id.contact_name']
        return ['name']

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('sales_code'):
                    v['sales_code'] = self.env['ir.sequence'].next_by_code(
                        'sales.sales_order') or '/'
            return super(sales_order, self).create(vals)
        if not vals.get('sales_code'):
            vals['sales_code'] = self.env['ir.sequence'].next_by_code(
                'sales.sales_order') or '/'

        res = super(sales_order, self).create(vals)

        if 'order_line_ids' in vals:
            res._check_approval_requirement()
        res._refresh_line_indent_flags()

        return res

    @api.depends('order_line_ids.sub_total')
    def _compute_total_amount(self):
        for record in self:
            total = sum(line.sub_total for line in record.order_line_ids)
            tax_amount = 0.0
            for line in record.order_line_ids:
                if line.taxes:
                    tax_amount += line.sub_total * \
                        (line.taxes.tax_percentage / 100)
            total += tax_amount
            record.total_amount_untaxed = total - tax_amount
            record.total_tax = tax_amount
            record.total_amount = total

    @api.depends('invoice_ids.state')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids.filtered(
                lambda invoice: invoice.state != 'cancel'
            ))

    @api.depends('state', 'invoice_ids.state', 'invoice_ids.invoice_type')
    def _compute_invoice_status(self):
        for record in self:
            active_invoices = record.invoice_ids.filtered(
                lambda invoice: invoice.state != 'cancel'
            )
            regular_invoices = active_invoices.filtered(
                lambda invoice: invoice.invoice_type == 'regular'
            )
            if regular_invoices:
                record.invoice_status = 'invoiced'
            elif record.state == 'sale':
                record.invoice_status = 'to_invoice'
            else:
                record.invoice_status = 'no'

    def action_quotation_send_custom(self):
        self.ensure_one()

        target_customer = self.env['sales.customer'].search([
            ('id', '=', self.customer_id.id)
        ], limit=1)
        template = self.env.ref(
            'sales.email_template_compressor_quotation', raise_if_not_found=False)

        ctx = {
            'default_model': 'sales.sales_order',
            'default_res_ids': [self.id],
            'default_use_template': bool(template),
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'redirect_to_tree': 'sales.quotation_action',
            # PRE-FILL: Use the 'default_' + field_name syntax
            'default_customer_ids': [(6, 0, target_customer.ids if target_customer else [])],
            # Also ensure show_email is passed for display_name logic
            'show_email_in_wizard': True,
        }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Email',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def action_create_invoice_simple(self):
        self.ensure_one()
        self._check_invoicing_access()
        if self.state != 'sale':
            raise UserError(
                _("Invoice can only be created from a confirmed sales order.")
            )

        draft_invoice = self.invoice_ids.filtered(
            lambda invoice: invoice.state == 'draft'
        )[:1]
        if draft_invoice:
            return self.action_view_custom_invoice(draft_invoice)

        return {
            'name': _('Create Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.create.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sales_order_id': self.id,
            },
        }

    def action_view_custom_invoice(self, invoices=False):
        self.ensure_one()
        invoices = invoices or self.invoice_ids.filtered(
            lambda invoice: invoice.state != 'cancel'
        )
        action = self.env.ref('sales.sales_invoice_action').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _message_post_after_hook(self, message, msg_vals):
        # Logika untuk mengubah state setelah email terkirim
        if self.env.context.get('mark_so_as_sent') and self.state in ['draft', 'approved']:
            self.sudo().write({'state': 'sent'})
        return super(sales_order, self)._message_post_after_hook(message, msg_vals)

    def action_confirm(self):
        self.ensure_one()
        self.state = 'sale'

    def action_cancel(self):
        self.ensure_one()
        self._check_cancel_order_access()
        self.state = 'cancel'

    def _check_cancel_order_access(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            return
        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        cancel_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'sales_order'),
            ('can_delete', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)
        if not cancel_authorized:
            raise UserError(
                _("You do not have access rights to cancel sales orders."))

    def action_open_discount_wizard(self):
        self.ensure_one()
        return {
            'name': 'Discount',
            'type': 'ir.actions.act_window',
            'res_model': 'sales.discount_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sales_order_id': self.id},
        }

    def action_delete_sales(self):
        self.ensure_one()
        if self.invoice_ids.filtered(lambda invoice: invoice.state != 'cancel'):
            raise UserError(
                _("This sales order cannot be deleted because it already has custom invoices.")
            )
        self.unlink()

        return self.action_back_to_quotations()

    def action_back_to_quotations(self):
        self.ensure_one()
        return {
            'name': 'Quotation',
            'type': 'ir.actions.act_window',
            'res_model': 'sales.sales_order',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'domain': [('state', 'in', ['draft', 'wait_approval', 'approved', 'sent', 'cancel']), ('is_quotation', '=', True)],
            'context': self.env.context,
        }

    def action_back_to_sales(self):
        self.ensure_one()
        return {
            'name': 'Sales Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'sales.sales_order',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'domain': ['|', '&', ('is_quotation', '=', False), ('state', 'in', ['sale', 'sale_draft', 'wait_approval', 'approved', 'cancel']), '&', ('is_quotation', '=', True), ('state', '=', 'sale')],
            'context': self.env.context,
        }

    def action_back_to_approvals(self):
        self.ensure_one()
        return {
            'name': 'Waiting My Approval',
            'type': 'ir.actions.act_window',
            'res_model': 'sales.sales_order',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'domain': [('current_approver', '=', self.env.uid), ('state', 'in', ['wait_approval'])],
            'help': """
                <p class="o_view_nocontent_smiling_face">
                    No quotations waiting for your approval.
                </p>
            """,
            'context': {'search_default_filter_to_approve': 1, 'create': False, 'is_approval_view': True},
        }

    def _prepare_regular_invoice_line_vals(self, sequence):
        self.ensure_one()
        line_values = []
        for line in self.order_line_ids:
            tax_percentage = line.taxes.tax_percentage if line.taxes else 0.0
            line_values.append((0, 0, {
                'sequence': sequence,
                'sales_order_line_id': line.id,
                'product_id': line.product_id.id,
                'description': line.product_id.product_name if line.product_id else line.info or self.sales_code,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'discount': line.discount,
                'tax_id': line.taxes.id if line.taxes else False,
                'tax_percentage': tax_percentage,
                'source_subtotal': line.sub_total,
            }))
            sequence += 1
        previous_payments = self.invoice_ids.filtered(
            lambda invoice: invoice.state != 'cancel'
        ).mapped('payment_ids').filtered(
            lambda payment: payment.state == 'posted'
        ).sorted(lambda payment: (payment.payment_date or fields.Date.today(), payment.id))
        if previous_payments:
            line_values.append((0, 0, {
                'sequence': sequence,
                'description': _('Previous Payments'),
                'display_type': 'line_section',
            }))
            sequence += 1
            for payment in previous_payments:
                payment_label = _(
                    '%(number)s - %(date)s - %(amount)s',
                    number=payment.payment_number or '-',
                    date=payment.payment_date.strftime(
                        '%d/%m/%Y') if payment.payment_date else '-',
                    amount='Rp {:,.0f}'.format(payment.amount or 0.0),
                )
                if payment.memo:
                    payment_label = _(
                        '%(label)s - %(memo)s',
                        label=payment_label,
                        memo=payment.memo,
                    )
                line_values.append((0, 0, {
                    'sequence': sequence,
                    'description': payment_label,
                    'display_type': 'line_note',
                }))
                sequence += 1
        return line_values

    def _prepare_down_payment_invoice_line_vals(self, invoice_type, percentage=0.0, fixed_amount=0.0, sequence=1):
        self.ensure_one()
        order_lines = self.order_line_ids.filtered(
            lambda line: line.quantity > 0)
        if not order_lines:
            raise UserError(
                _("Please add at least one order line before creating an invoice."))

        gross_total = sum(
            line.sub_total *
            (1 + ((line.taxes.tax_percentage if line.taxes else 0.0) / 100.0))
            for line in order_lines
        )
        if gross_total <= 0:
            raise UserError(
                _("The sales order total must be greater than zero to create a down payment invoice."))

        target_total = fixed_amount
        if invoice_type == 'down_payment_percentage':
            target_total = gross_total * (percentage / 100.0)

        if target_total <= 0:
            raise UserError(
                _("The down payment amount must be greater than zero."))
        if target_total > gross_total:
            raise UserError(
                _("The down payment amount cannot be greater than the sales order total."))

        line_values = []
        remaining_gross = target_total
        order_lines_count = len(order_lines)

        for index, line in enumerate(order_lines, start=1):
            tax_percentage = line.taxes.tax_percentage if line.taxes else 0.0
            line_gross = line.sub_total * (1 + (tax_percentage / 100.0))

            if index == order_lines_count:
                gross_share = remaining_gross
            else:
                gross_share = round(
                    target_total * (line_gross / gross_total), 0)
                remaining_gross -= gross_share

            divisor = 1 + (tax_percentage / 100.0)
            untaxed_share = round(gross_share / divisor,
                                  0) if divisor else gross_share

            line_values.append((0, 0, {
                'sequence': sequence,
                'sales_order_line_id': line.id,
                'product_id': line.product_id.id,
                'description': _(
                    "Down Payment - %(product)s",
                    product=line.product_id.product_name if line.product_id else self.sales_code,
                ),
                'quantity': 1,
                'unit_price': untaxed_share,
                'discount': 0.0,
                'tax_id': line.taxes.id if line.taxes else False,
                'tax_percentage': tax_percentage,
                'source_subtotal': line.sub_total,
            }))
            sequence += 1

        return line_values

    def _prepare_custom_invoice_vals(self, invoice_type, percentage=0.0, fixed_amount=0.0):
        self.ensure_one()
        invoice_vals = {
            'sales_order_id': self.id,
            'customer_id': self.customer_id.id,
            'customer_address': self.address,
            'delivery_date': self.commitment_date,
            'invoice_date': fields.Date.today(),
            'invoice_type': invoice_type,
            'sales_name': self.sales_name.id,
            'payment_terms_id': self.payment_terms.id,
            'order_date': self.date_ordered or self.quotation_date,
            'line_ids': [],
        }
        if invoice_type == 'regular':
            invoice_vals['line_ids'] = self._prepare_regular_invoice_line_vals(
                1)
        else:
            invoice_vals['percentage'] = percentage
            invoice_vals['fixed_amount'] = fixed_amount
            invoice_vals['line_ids'] = self._prepare_down_payment_invoice_line_vals(
                invoice_type, percentage=percentage, fixed_amount=fixed_amount, sequence=1
            )
        return invoice_vals

    def create_custom_invoice(self, invoice_type, percentage=0.0, fixed_amount=0.0):
        self.ensure_one()
        if self.state != 'sale':
            raise UserError(
                _("Invoice can only be created from a confirmed sales order."))
        if not self.order_line_ids:
            raise UserError(
                _("Please add at least one order line before creating an invoice."))

        existing_draft = self.invoice_ids.filtered(
            lambda invoice: invoice.state == 'draft')
        if existing_draft:
            raise UserError(
                _("This sales order already has a draft invoice. Please confirm or cancel it first."))

        if invoice_type in ('down_payment_percentage', 'down_payment_fixed') and self.invoice_ids.filtered(
            lambda invoice: invoice.state != 'cancel' and invoice.invoice_type == 'regular'
        ):
            raise UserError(
                _("Down payment invoice cannot be created after a regular invoice already exists."))

        return self.env['sales.invoice'].create(
            self._prepare_custom_invoice_vals(
                invoice_type,
                percentage=percentage,
                fixed_amount=fixed_amount,
            )
        )

    @api.onchange('customer_id')
    def _onchange_customer_id_payment_terms(self):
        if self.customer_id:
            # Mengambil payment terms dari model customer
            # Pastikan field 'payment_terms_id' ada di model sales.customer
            self.payment_terms = self.customer_id.payment_terms
        else:
            self.payment_terms = False

    @api.model
    def default_get(self, fields_list):
        res = super(sales_order, self).default_get(fields_list)

        # Cek apakah field 'note' ada dalam list field yang diminta
        if 'note' in fields_list:
            # Cari record Syarat & Ketentuan (mengambil yang pertama ditemukan)
            terms = self.env['sales.terms_and_conditions'].search([], limit=1)
            if terms:
                # Ganti 'terms_field_name' dengan nama field teks di model terms Anda
                # Misal nama field-nya adalah 'description' atau 'content'
                res.update({
                    'note': terms.content  # Ganti 'content' dengan nama field yang sesuai
                })

        return res

    def write(self, vals):
        res = super(sales_order, self).write(vals)

        if res and 'order_line_ids' in vals:
            self._check_approval_requirement()
        if res and ('order_line_ids' in vals or 'state' in vals):
            self._refresh_line_indent_flags()

        return res

    def _refresh_line_indent_flags(self):
        """Perbarui label Indent pada baris SO setelah create/update."""
        for order in self.filtered(lambda o: o.state in RESERVED_SO_STATES):
            for line in order.order_line_ids:
                if not line.product_id:
                    if line.info:
                        line.info = ""
                    continue
                free = max(0, line.product_id.stock -
                           line.product_id.qty_reserved_sale)
                demand = sum(
                    (l.quantity or 0) for l in order.order_line_ids
                    if l.product_id == line.product_id)
                new_info = "Indent" if demand > free else ""
                if line.info != new_info:
                    line.write({'info': new_info})

    def _check_approval_requirement(self):
        for record in self:
            needs_approval = False
            reason1 = ""
            reason2 = ""

            # LOGIKA: Cek apakah total_amount melebihi min_amount di sales_approval_matrix yang terkecil atau sama dengan total_amount
            amount_exceeded = self.env['sales.sales_approval_matrix'].search(
                [('min_amount', '<', record.total_amount), ('min_amount', '>', 0)], order='sequence', limit=1)
            if amount_exceeded:
                record.need_approval = True
                needs_approval = True
                reason1 = f"Total amount {record.total_amount:,.0f} exceeds the minimum threshold of {amount_exceeded.min_amount:,.0f} for approval."

            # Periksa apakah ada diskon yang melebihi base_discount
            for line in record.order_line_ids:
                if line.discount > line.base_discount:
                    needs_approval = True
                    reason2 = f"There are items that have a discount of {line.discount}% which exceeds the base discount of {line.base_discount}%."
                    break

            # LOGIKA: Jika Butuh Approval (Diskon > Base)
            if needs_approval:
                if record.approval_log_ids:
                    record.approval_log_ids.filtered(
                        lambda log: log.state == 'pending').unlink()

                # Ambil sequence dari data matrix yang memiliki min_amount > total_amount
                max_sequence = self.env['sales.sales_approval_matrix'].search(
                    [('min_amount', '>', record.total_amount)], order='sequence asc', limit=1).sequence

                if not max_sequence:
                    matrix_data = self.env['sales.sales_approval_matrix'].search(
                        [], order='sequence asc')
                else:
                    matrix_data = self.env['sales.sales_approval_matrix'].search(
                        [('sequence', '<', max_sequence)], order='sequence asc')

                if matrix_data:
                    log_lines = []
                    for matrix in matrix_data:
                        if log_lines == []:
                            if reason1 and reason2:
                                approval_reason = f"Total amount {record.total_amount:,.0f} exceeds the minimum threshold of {amount_exceeded.min_amount:,.0f} for approval, and there are items that have a discount of {line.discount}% which exceeds the base discount of {line.base_discount}%."
                            elif reason1:
                                approval_reason = reason1
                            elif reason2:
                                approval_reason = reason2

                            log_lines.append((0, 0, {
                                'user_id': matrix.name.user_id.id if matrix.name.user_id else None,
                                'approver': matrix.name.name,
                                'email': matrix.name.user_id.login if matrix.name.user_id else '',
                                'position': matrix.position.position_name if matrix.position else '',
                                'sequence': matrix.sequence,  # Sequence sesuai dengan data matrix
                                'min_amount': matrix.min_amount,
                                'receive_return': matrix.receive_return,
                                'approve': matrix.approve,
                                'revise': matrix.revise,
                                'returned': matrix.returned,
                                'reject': matrix.reject,
                                'printed': matrix.printed,
                                'notify': matrix.notify,
                                'approved_as': matrix.approved_as,
                                'state': 'pending',  # Pastikan state log mulai dari pending
                                'approval_reason': approval_reason,  # Simpan alasan approval di log pertama
                            }))
                        else:
                            log_lines.append((0, 0, {
                                'user_id': matrix.name.user_id.id if matrix.name.user_id else None,
                                'approver': matrix.name.name,
                                'email': matrix.name.user_id.login if matrix.name.user_id else '',
                                'position': matrix.position.position_name if matrix.position else '',
                                'sequence': matrix.sequence,  # Tambahkan offset untuk memastikan urutan log
                                'min_amount': matrix.min_amount,
                                'receive_return': matrix.receive_return,
                                'approve': matrix.approve,
                                'revise': matrix.revise,
                                'returned': matrix.returned,
                                'reject': matrix.reject,
                                'printed': matrix.printed,
                                'notify': matrix.notify,
                                'approved_as': matrix.approved_as,
                                'state': 'pending',  # Pastikan state log mulai dari pending
                            }))

                    super(sales_order, record).write({
                        'approval_log_ids': log_lines,
                        # Tetap di draft/sale_draft sampai user submit untuk approval
                        'state': 'draft' if record.is_quotation else 'sale_draft'
                    })

            # LOGIKA: Jika diskon dikembalikan ke normal (<= base)
            else:
                if record.approval_log_ids:
                    record.approval_log_ids.filtered(
                        lambda log: log.state == 'pending').unlink()
                    # Kembalikan ke draft jika log dihapus
                    if record.state == 'wait_approval':
                        super(sales_order, record).write(
                            {'state': 'draft' if record.is_quotation else 'sale_draft'})

    def action_submit_for_approval(self):
        self.ensure_one()
        if self.state != 'draft' and self.state != 'sale_draft':
            raise UserError(
                _("Only quotations/sales orders in 'Draft' state can be submitted for approval."))
        self.state = 'wait_approval'
        self._send_approval_notification()
        approver_user = self.env['res.users'].search(
            [('id', '=', self.current_approver)], limit=1)

        # if approver_user:
        # Buat Aktivitas (Notification Badge otomatis muncul)
        # self.activity_schedule(
        #     'sales.mail_act_sales_approval',  # ID XML dari langkah 1
        #     user_id=approver_user.id,
        #     note=f"Mohon periksa Quotation {self.sales_code} untuk disetujui."
        # )

    def action_approve(self):
        self.ensure_one()
        if self.state != 'wait_approval':
            raise UserError(
                _("Only quotations in 'Waiting Approval' state can be approved."))

        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending'
        ).sorted('sequence')

        if not current_log or current_log[0].user_id != self.env.uid:
            raise UserError(
                _("You are not authorized to approve this document at this stage."))

        return {
            'name': _('Confirmation of Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sales_order_id': self.id},
        }

    def action_approve_final(self):
        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending'
        ).sorted('sequence')

        if current_log:
            log = current_log[0]
            if log.user_id == self.env.uid:
                log.write({
                    'state': 'approved',
                    'action_date': fields.Datetime.now()
                })
            else:
                raise UserError(
                    _("You are not authorized to approve this document at this stage."))

        # Jika semua log sudah 'approved', baru ubah status Sales Order ke 'approved'
        remaining_logs = self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending')

        if not remaining_logs:
            self.state = 'approved'
            # Opsional: Jika ingin langsung ke 'sent' setelah full approval
            # self.state = 'sent'
        else:
            if self.state == 'wait_approval':
                # Kirim email ke approver selanjutnya dalam sequence
                self._send_approval_notification()

        return self.action_back_to_approvals()

    def action_revise(self):
        # Panggil action edit untuk membuka form dengan mode edit
        self.ensure_one()
        self.is_revised = True  # Tandai bahwa ini adalah revisi
        if self.state not in ['wait_approval']:
            raise UserError(
                _("Only quotations in 'Waiting Approval' state can be revised."))
        return self.action_edit()

    def action_save_revised(self):
        self.ensure_one()
        if self.state not in ['wait_approval']:
            raise UserError(
                _("Only quotations in 'Waiting Approval' state can be revised."))

        return {
            'name': _('Quotation Revised'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.revise.wizard',
            'view_mode': 'form',
            'target': 'new',  # Ini akan membuka pop-up
            'context': {'default_sales_order_id': self.id},
        }

    def action_return(self):
        self.ensure_one()
        if self.state != 'wait_approval':
            raise UserError(
                _("Only quotations in 'Waiting Approval' state can be returned."))

        return {
            'name': _('Please Provide Return Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.return.wizard',
            'view_mode': 'form',
            'target': 'new',  # Ini akan membuka pop-up
            'context': {'default_sales_order_id': self.id},
        }

    def action_reject(self):
        self.ensure_one()
        # Validasi state sebelum buka wizard
        if self.state != 'wait_approval':
            raise UserError(
                _("Only quotations in 'Waiting Approval' state can be rejected."))

        return {
            'name': _('Please Provide Reject Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.reject.wizard',
            'view_mode': 'form',
            'target': 'new',  # Ini akan membuka pop-up
            'context': {'default_sales_order_id': self.id},
        }

    def action_reject_final(self):
        self.ensure_one()
        reason = self.env.context.get('reject_reason')

        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.user_id == self.env.uid and l.state == 'pending'
        )

        if not current_log:
            raise UserError(
                _("You are not authorized to reject this document."))

        # Update log dengan alasan dari wizard
        current_log.write({
            'state': 'rejected',
            'action_date': fields.Datetime.now(),
            'note': reason
        })

        self.write({
            'state': 'cancel',
            'approval_status': 'rejected'
        })

        # Kirim notifikasi ke salesman (jika sudah ada fungsinya)
        if hasattr(self, '_send_salesman_notification'):
            self._send_salesman_notification(note=reason)

        return self.action_back_to_approvals()

    def action_revise_final(self):
        self.ensure_one()
        message = self.env.context.get('revise_message')
        self.is_revised = False  # Reset flag revisi setelah simpan
        self.is_edit = False  # Pastikan mode edit dimatikan setelah revisi

        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.user_id == self.env.uid and l.state == 'pending'
        )

        if not current_log:
            raise UserError(
                _("You are not authorized to revise this document."))

        self.approval_log_ids.sudo().create({
            'sales_order_id': self.id,
            'user_id': self.env.uid,
            'approver': current_log[0].approver,
            'email': current_log[0].email,
            'position': current_log[0].position,
            'sequence': current_log[0].sequence,
            'min_amount': current_log[0].min_amount,
            'receive_return': current_log[0].receive_return,
            'approve': current_log[0].approve,
            'revise': current_log[0].revise,
            'returned': current_log[0].returned,
            'reject': current_log[0].reject,
            'printed': current_log[0].printed,
            'notify': current_log[0].notify,
            'approved_as': current_log[0].approved_as,
            'state': 'revised',
            'action_date': fields.Datetime.now(),
            'note': message
        })

        # Kirim notifikasi ke salesman (jika sudah ada fungsinya)
        if hasattr(self, '_send_salesman_notification'):
            self._send_salesman_notification(note=message)

        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', self._name),
            ('type', '=', 'form')
        ], limit=1).id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Waiting My Approval',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(view_id, 'form')],
            'target': 'current',
            'context': {'is_approval_view': True, 'create': False, 'search_default_filter_to_approve': 1},
            'domain': [('id', '=', self.id)],
        }

    def action_return_final(self):
        self.ensure_one()
        reason = self.env.context.get('return_reason')
        draft = False

        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.user_id == self.env.uid and l.state == 'pending'
        )

        if not current_log:
            raise UserError(
                _("You are not authorized to return this document."))

        # Update log dengan alasan dari wizard
        current_log.write({
            'state': 'returned',
            'action_date': fields.Datetime.now(),
            'note': reason
        })

        # Hapus log yang masih pending (jika ada) untuk reset approval flow
        self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending').unlink()

        # Cek apakah ada approver yang menerima return (receive_return = True) pada matrix dengan sequence lebih rendah dari user yang melakukan return
        return_matrix = self.env['sales.sales_approval_matrix'].sudo().search([
            ('receive_return', '=', True),
            ('sequence', '<', self.env['sales.sales_approval_matrix'].sudo().search(
                [('sequence', '=', self.approval_log_ids.sudo().search([('user_id', '=', self.env.uid), ('sales_order_id', '=', self.id)], limit=1, order='id desc').sequence)], limit=1).sequence)
        ], order='sequence asc', limit=1)

        max_sequence = self.env['sales.sales_approval_matrix'].search(
            [('min_amount', '>', self.total_amount)], order='sequence asc', limit=1).sequence

        if return_matrix:
            if max_sequence:
                approvers = self.env['sales.sales_approval_matrix'].sudo().search([
                    ('sequence', '>=', return_matrix.sequence),
                    ('sequence', '<', max_sequence)
                ])
            else:
                approvers = self.env['sales.sales_approval_matrix'].sudo().search([
                    ('sequence', '>=', return_matrix.sequence)
                ])
        else:
            if max_sequence:
                approvers = self.env['sales.sales_approval_matrix'].sudo().search([
                    ('sequence', '<', max_sequence)
                ])
            else:
                approvers = self.env['sales.sales_approval_matrix'].sudo().search([
                ])
            draft = True  # Jika tidak ada matrix yang menerima return, langsung ke draft

        for approver in approvers:
            self.approval_log_ids.create({
                'sales_order_id': self.id,
                'user_id': approver.name.user_id.id if approver.name.user_id else None,
                'approver': approver.name.name,
                'email': approver.name.user_id.login if approver.name.user_id else '',
                'position': approver.position.position_name if approver.position else '',
                'sequence': approver.sequence,
                'min_amount': approver.min_amount,
                'receive_return': approver.receive_return,
                'approve': approver.approve,
                'revise': approver.revise,
                'returned': approver.returned,
                'reject': approver.reject,
                'printed': approver.printed,
                'notify': approver.notify,
                'approved_as': approver.approved_as,
                'state': 'pending',
            })

        if draft:
            self.write({
                'state': 'draft' if self.is_quotation else 'sale_draft',
                'approval_status': 'pending'
            })

        # Kirim notifikasi ke salesman (jika sudah ada fungsinya)
        if hasattr(self, '_send_salesman_notification'):
            self._send_salesman_notification(note=reason)

        return self.action_back_to_approvals()

    def _compute_submit_permissions(self):
        self.user_can_submit = False
        current_user_id = self.env.uid
        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', current_user_id)
        ], limit=1)
        submit_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', 'in', ['quotation', 'sales_order']),
            ('can_submit', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if submit_authorized:
            for rec in self:
                rec.user_can_submit = True

    def _compute_send_permissions(self):
        self.user_can_send = False
        current_user_id = self.env.uid
        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', current_user_id)
        ], limit=1)
        send_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', 'in', ['quotation', 'sales_order']),
            ('can_send', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if send_authorized:
            for rec in self:
                rec.user_can_send = True

    def _compute_confirm_permissions(self):
        self.user_can_confirm = False
        current_user_id = self.env.uid
        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', current_user_id)
        ], limit=1)
        confirm_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', 'in', ['quotation', 'sales_order']),
            ('can_confirm', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if confirm_authorized:
            for rec in self:
                rec.user_can_confirm = True

    def _compute_invoicing_permissions(self):
        self.user_can_invoicing = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_invoicing = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        invoicing_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'sales_order'),
            ('can_invoicing', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if invoicing_authorized:
            for rec in self:
                rec.user_can_invoicing = True

    def _check_invoicing_access(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        invoicing_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'sales_order'),
            ('can_invoicing', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)
        if not invoicing_authorized:
            raise UserError(
                _("You do not have access rights to perform invoicing actions."))

    # Tambahkan dependency yang relevan
    @api.depends('state', 'approval_log_ids')
    def _compute_approval_permissions(self):
        # 1. Inisialisasi SEMUA record dengan False di awal (Sangat Penting)
        self.user_can_approve = False
        self.user_can_revise = False
        self.user_can_return = False
        self.user_can_reject = False

        # 2. Cari data user & matrix sekali saja (Optimasi)
        current_user_id = self.env.uid
        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', current_user_id)
        ], limit=1)

        if current_custom_user:
            matrix_line = self.env['sales.sales_approval_matrix'].sudo().search([
                ('name', '=', current_custom_user.id)
            ], limit=1)

            # 3. Jika matrix ditemukan, baru isi nilai True pada record yang sesuai
            if matrix_line:
                for rec in self:
                    rec.user_can_approve = matrix_line.approve
                    rec.user_can_revise = matrix_line.revise
                    rec.user_can_return = matrix_line.returned
                    rec.user_can_reject = matrix_line.reject

    @api.depends('approval_log_ids.state')
    def _compute_current_approver(self):
        for rec in self:
            # Filter log yang masih pending dan urutkan berdasarkan sequence
            pending_logs = rec.approval_log_ids.filtered(
                lambda l: l.state == 'pending'
            ).sorted('sequence')

            if pending_logs:
                # Ambil approver pertama dalam antrian
                rec.current_approver = pending_logs[0].user_id
                rec.current_approver_name = pending_logs[0].approver
            else:
                rec.current_approver = False
                rec.current_approver_name = False

    def _send_approval_notification(self):
        self.ensure_one()
        template = self.env.ref(
            'sales.email_template_sales_approval_request', raise_if_not_found=False)
        if not template:
            return

        # Cari log yang pending dengan urutan terkecil (Next Approver)
        next_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending'
        ).sorted('id')

        if next_log:
            log = next_log[0]
            if log.email:
                # Masukkan data dinamis ke dalam Context agar dibaca oleh Template
                ctx = {
                    'email_to': log.email,
                    'approver_name': log.approver,
                    'position': log.position,
                }
                template.with_context(ctx).send_mail(self.id, force_send=True)
                # Tandai di log bahwa email sudah terkirim
                log.sudo().write({'mail_sent': True})

    def _compute_need_approval(self):
        for record in self:
            record.need_approval = any(
                line.discount > line.base_discount for line in record.order_line_ids)

        for record in self:
            amount_exceeded = self.env['sales.sales_approval_matrix'].search(
                [('min_amount', '<', record.total_amount), ('min_amount', '>', 0)], order='sequence asc', limit=1)
            if amount_exceeded:
                record.need_approval = True


class SalesApproveWizard(models.TransientModel):
    _name = 'sales.approve.wizard'
    _description = 'Confirmation of Approval'

    sales_order_id = fields.Many2one('sales.sales_order', string="Sales Order")
    message = fields.Text(
        readonly=True, default="Are you sure you want to accept this order? This action will proceed to the next step.")

    def action_confirm(self):
        self.ensure_one()
        # Memanggil fungsi approval final di model utama
        return self.sales_order_id.action_approve_final()


class SalesRejectWizard(models.TransientModel):
    _name = 'sales.reject.wizard'
    _description = 'Reject Reason Wizard'

    sales_order_id = fields.Many2one('sales.sales_order', string="Sales Order")
    reason = fields.Text(string="Reject Reason", required=True)

    def action_reject_confirm(self):
        self.ensure_one()
        # Panggil fungsi reject asli di sales_order dengan membawa alasan
        return self.sales_order_id.with_context(reject_reason=self.reason).action_reject_final()


class SalesReturnWizard(models.TransientModel):
    _name = 'sales.return.wizard'
    _description = 'Return Reason Wizard'

    sales_order_id = fields.Many2one('sales.sales_order', string="Sales Order")
    reason = fields.Text(string="Return Reason", required=True)

    def action_return_confirm(self):
        self.ensure_one()
        # Panggil fungsi return asli di sales_order dengan membawa alasan
        return self.sales_order_id.with_context(return_reason=self.reason).action_return_final()


class SalesReviseWizard(models.TransientModel):
    _name = 'sales.revise.wizard'
    _description = 'Revise Confirmation Wizard'

    sales_order_id = fields.Many2one('sales.sales_order', string="Sales Order")
    message = fields.Text(string="Revise Message", required=True)

    def action_revise_confirm(self):
        self.ensure_one()
        # Panggil fungsi revise asli di sales_order dengan membawa pesan revisi (jika diperlukan)
        return self.sales_order_id.with_context(revise_message=self.message).action_revise_final()


class sales_order_line(models.Model):
    _name = 'sales.sales_order_line'
    _description = 'Sales Order Line'

    sales_order_id = fields.Many2one(
        comodel_name='sales.sales_order', string='Sales Order', ondelete='cascade', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product', ondelete='set null', index=True,
        domain=[('sales_ok', '=', True)])
    quantity = fields.Integer(string="Quantity", default=1)
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM")
    unit_price = fields.Float(string="Unit Price", digits=(16, 0), store=True)
    taxes = fields.Many2one(related='product_id.customer_tax', string="Taxes")
    base_discount = fields.Float(string="Base Disc.%", default=0.0)
    discount = fields.Float(string="Disc.%", default=0.0)
    sub_total = fields.Float(
        string="Sub Total (Tax excl.)", compute='_compute_total_price', store=True, digits=(16, 0))
    info = fields.Char(string="Info")

    @api.depends('quantity', 'unit_price', 'discount')
    def _compute_total_price(self):
        for record in self:
            record.sub_total = record.quantity * \
                record.unit_price * (1 - record.discount / 100)

    def _free_stock_after_reservations(self, product):
        """Stok fisik dikurangi qty yang di-book di SO terbuka (belum cancel)."""
        if not product:
            return 0
        return max(0, product.stock - product.qty_reserved_sale)

    def _total_qty_this_order_for_product(self, product):
        order = self.sales_order_id
        if not order or not product:
            return self.quantity or 0
        return sum(
            (l.quantity or 0) for l in order.order_line_ids
            if l.product_id == product)

    def _set_indent_from_availability(self):
        """Indent jika total kebutuhan produk di SO ini melebihi stok bebas."""
        if not self.product_id:
            self.info = ""
            return
        free = self._free_stock_after_reservations(self.product_id)
        demand = self._total_qty_this_order_for_product(self.product_id)
        self.info = "Indent" if demand > free else ""

    @api.onchange('product_id')
    def _onchange_product_id_price_condition(self):
        if not self.product_id:
            return

        self._set_indent_from_availability()

        self.unit_price = self.product_id.base_price

        if not self.sales_order_id.customer_id:
            self.discount = 0.0
            self.base_discount = 0.0
            return

        now = fields.Datetime.now()
        customer = self.sales_order_id.customer_id
        product = self.product_id

        domain = [
            '|',
            ('date_start', '=', False),
            '&',
            ('date_start', '<=', now),
            ('date_end', '>=', now),
            '|', '|',
            ('customer_applied_on', '=', 'all'),
            ('customer_category_ids', 'in', [customer.cust_category.id]),
            ('customer_ids.customer_id', '=', customer.id),
            ('min_quantity', '<=', self.quantity)
        ]

        # Urutkan berdasarkan ID desc agar mengambil settingan terbaru jika ada double
        conditions = self.env['sales.price_condition'].search(
            domain, order='customer_priority asc, product_priority asc, id desc')

        self.unit_price = product.base_price
        self.discount = 0.0
        self.base_discount = 0.0

        for condition in conditions:
            apply_price = False

            # 2. Cek apakah produk ini termasuk dalam kondisi
            if condition.applied_on == 'all':
                apply_price = True
            elif condition.applied_on == 'category' and product.product_category in condition.product_category_ids:
                apply_price = True
            elif condition.applied_on == 'product':
                # Cek di child table price_condition_product
                product_line = condition.product_ids.filtered(
                    lambda l: l.product_id == product)
                if product_line:
                    apply_price = True

            # 3. Jika cocok, terapkan harga/diskon
            if apply_price:
                if condition.compute_price == 'fixed':
                    self.unit_price = condition.fixed_price
                    self.discount = 0.0
                    self.base_discount = 0.0

                elif condition.compute_price == 'discount':
                    self.unit_price = product.base_price
                    self.discount = condition.percent_price
                    self.base_discount = condition.percent_price

                # Berhenti di condition pertama yang paling cocok (paling baru)
                break

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.mapped('sales_order_id')._refresh_line_indent_flags()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'product_id', 'quantity'} & set(vals.keys()):
            self.mapped('sales_order_id')._refresh_line_indent_flags()
        return res

    @api.model
    def default_get(self, fields_list):
        res = super(sales_order_line, self).default_get(fields_list)

        return res

    @api.onchange('quantity')
    def _onchange_quantity(self):
        if not self.product_id or not self.sales_order_id or not self.sales_order_id.customer_id:
            self._set_indent_from_availability()
            return

        self._set_indent_from_availability()

        now = fields.Datetime.now()
        customer = self.sales_order_id.customer_id
        product = self.product_id

        domain = [
            '|',
            ('date_start', '=', False),
            '&',
            ('date_start', '<=', now),
            ('date_end', '>=', now),
            '|', '|',
            ('customer_applied_on', '=', 'all'),
            ('customer_category_ids', 'in', [customer.cust_category.id]),
            ('customer_ids.customer_id', '=', customer.id),
            ('min_quantity', '<=', self.quantity)
        ]

        # Urutkan berdasarkan ID desc agar mengambil settingan terbaru jika ada double
        conditions = self.env['sales.price_condition'].search(
            domain, order='customer_priority asc, product_priority asc, id desc')

        self.base_discount = 0.0

        for condition in conditions:
            apply_price = False

            # 2. Cek apakah produk ini termasuk dalam kondisi
            if condition.applied_on == 'all':
                apply_price = True
            elif condition.applied_on == 'category' and product.product_category in condition.product_category_ids:
                apply_price = True
            elif condition.applied_on == 'product':
                # Cek di child table price_condition_product
                product_line = condition.product_ids.filtered(
                    lambda l: l.product_id == product)
                if product_line:
                    apply_price = True

            # 3. Jika cocok, terapkan harga/diskon
            if apply_price:
                if condition.compute_price == 'fixed':
                    self.unit_price = condition.fixed_price
                    self.base_discount = 0.0

                elif condition.compute_price == 'discount':
                    self.unit_price = product.base_price
                    self.discount = condition.percent_price if condition.percent_price > self.discount else self.discount
                    self.base_discount = condition.percent_price

                # Berhenti di condition pertama yang paling cocok (paling baru)
                break


class taxes(models.Model):
    _name = 'sales.taxes'
    _inherit = ['navigation.mixin']
    _description = 'Taxes'
    _menu_code = 'taxes'

    name = fields.Char(string='Tax Name', required=True)
    tax_percentage = fields.Float(string='Tax Percentage (%)', required=True)
    default_tax = fields.Boolean(string='Default Tax')
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if vals.get('default_tax'):
            # Reset default_tax for all other records
            current_defaults = self.sudo().search([('default_tax', '=', True)])
            current_defaults.sudo().write({'default_tax': False})
        return super(taxes, self).create(vals)

    def write(self, vals):
        if vals.get('default_tax'):
            # Reset default_tax for all other records
            current_defaults = self.sudo().search(
                [('default_tax', '=', True), ('id', '!=', self.id)])
            current_defaults.sudo().write({'default_tax': False})
        return super(taxes, self).write(vals)


class terms_and_conditions(models.Model):
    _name = 'sales.terms_and_conditions'
    _inherit = ['navigation.mixin']
    _description = 'Terms and Conditions'
    _menu_code = 'terms_and_conditions'

    content = fields.Text(string="Content")
    is_edit = fields.Boolean(default=False)


class sales_approval_matrix(models.Model):
    _name = 'sales.sales_approval_matrix'
    _inherit = ['navigation.mixin']
    _description = 'Sales Approval Matrix'
    _menu_code = 'sales_approval_matrix'

    name = fields.Many2one(
        comodel_name='general.custom_users', string='Approver', index=True, domain=[('menu_ids.menu_id', 'in', ['Sales Approval'])])
    sequence = fields.Integer(string="Sequence", default=1)
    position = fields.Many2one(related='name.position', string="Job Position")
    receive_return = fields.Boolean(string="Receive Return")
    min_amount = fields.Float(string="Minimum Amount",
                              digits=(16, 0), default=0)
    approve = fields.Boolean(string="Allow Approve", default=False)
    revise = fields.Boolean(string="Allow Revision", default=False)
    returned = fields.Boolean(string="Allow Return", default=False)
    reject = fields.Boolean(string="Allow Reject", default=False)
    printed = fields.Boolean(string="Allow Print", default=False)
    notify = fields.Boolean(string="Receive Notification", default=False)
    approved_as = fields.Selection([
        ('proposer', 'Proposer'),
        ('checker', 'Checker'),
        ('approver', 'Approver'),
        ('validator', 'Validator'),
        ('finalizer', 'Finalizer')
    ], string="Role in Approval", default='approver')
    is_edit = fields.Boolean(default=False)


class sales_approval_log(models.Model):
    _name = 'sales.sales_approval_log'
    _description = 'Sales Approval Log'
    _order = 'id asc'

    sales_order_id = fields.Many2one(
        comodel_name='sales.sales_order', string='Sales Order', ondelete='cascade', index=True)
    user_id = fields.Integer(string="Approver User ID")
    approver = fields.Char(string="Approver")
    email = fields.Char(string="Approver Email")
    position = fields.Char(string="Approver Position")
    action_date = fields.Datetime(string="Action Date")
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('revised', 'Revised'),
        ('returned', 'Returned'),
        ('rejected', 'Rejected')
    ], string="Approval State", default='pending')
    sequence = fields.Integer(string="Sequence", default=1)
    min_amount = fields.Float(string="Minimum Amount",
                              digits=(16, 0), default=0)
    receive_return = fields.Boolean(string="Receive Return")
    note = fields.Text(string="Comment")
    approval_reason = fields.Text(string="Reason for Approval Decision")
    mail_sent = fields.Boolean(string="Notification Sent", default=False)
    approve = fields.Boolean(string="Approve", default=False)
    revise = fields.Boolean(string="Revise", default=False)
    returned = fields.Boolean(string="Return", default=False)
    reject = fields.Boolean(string="Reject", default=False)
    printed = fields.Boolean(string="Print", default=False)
    notify = fields.Boolean(string="Notify", default=False)
    approved_as = fields.Char(string="Role in Approval")


class sales_invoice(models.Model):
    _name = 'sales.invoice'
    _description = 'Sales Invoice'
    _rec_name = 'invoice_number'
    _order = 'invoice_number desc, id desc'

    invoice_number = fields.Char(
        string="Invoice Number", readonly=True, copy=False)
    sales_order_id = fields.Many2one(
        comodel_name='sales.sales_order', string='Sales Order', ondelete='restrict', index=True, required=True)
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', ondelete='restrict', index=True, required=True)
    customer_address = fields.Text(string="Customer Address")
    document_type = fields.Selection([
        ('invoice', 'Invoice'),
        ('credit_note', 'Credit Note')
    ], string="Document Type", default='invoice', required=True)
    sales_name = fields.Many2one(
        comodel_name='general.custom_users', string='Salesperson', ondelete='set null', index=True)
    delivery_date = fields.Date(string="Delivery Date")
    payment_terms_id = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms', ondelete='set null', index=True)
    invoice_type = fields.Selection([
        ('regular', 'Regular Invoice'),
        ('down_payment_percentage', 'Down Payment (Percentage)'),
        ('down_payment_fixed', 'Down Payment (Fixed Amount)')
    ], string="Invoice Type", required=True, default='regular')
    invoice_date = fields.Date(
        string="Invoice Date", default=fields.Date.today, required=True)
    order_date = fields.Date(string="Order Date")
    posted_date = fields.Datetime(
        string="Posted On", readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')
    ], string="Status", default='draft')
    source_invoice_id = fields.Many2one(
        comodel_name='sales.invoice', string='Reversed Invoice', ondelete='set null', index=True)
    credit_note_ids = fields.One2many(
        'sales.invoice', 'source_invoice_id', string='Credit Notes')
    credit_note_count = fields.Integer(
        string='Credit Note Count', compute='_compute_credit_note_count')
    credit_note_reason = fields.Char(string="Credit Note Reason")
    percentage = fields.Float(string="Down Payment Percentage")
    fixed_amount = fields.Float(
        string="Down Payment Fixed Amount", digits=(16, 0))
    line_ids = fields.One2many(
        'sales.invoice.line', 'invoice_id', string='Invoice Lines')
    journal_item_ids = fields.One2many(
        'sales.invoice.journal.item', 'invoice_id', string='Journal Items')
    journal_item_count = fields.Integer(
        string='Journal Item Count', compute='_compute_journal_item_count')
    amount_untaxed = fields.Float(
        string="Untaxed Amount", compute='_compute_amounts', store=True, digits=(16, 0))
    amount_tax = fields.Float(
        string="Tax Amount", compute='_compute_amounts', store=True, digits=(16, 0))
    amount_total = fields.Float(
        string="Total", compute='_compute_amounts', store=True, digits=(16, 0))
    payment_ids = fields.One2many(
        'sales.payment', 'invoice_id', string='Payments')
    previous_payment_ids = fields.Many2many(
        'sales.payment', string='Previous Payments',
        compute='_compute_previous_payments')
    payment_count = fields.Integer(
        string='Payment Count', compute='_compute_payment_state', store=True)
    previous_payment_count = fields.Integer(
        string='Previous Payment Count', compute='_compute_previous_payments')
    amount_paid = fields.Float(
        string="Amount Paid", compute='_compute_payment_state', store=True, digits=(16, 0))
    amount_due = fields.Float(
        string="Amount Due", compute='_compute_payment_state', store=True, digits=(16, 0))
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ], string="Payment Status", compute='_compute_payment_state', store=True, default='not_paid')
    payment_terms_note = fields.Html(
        string="Payment Terms Note", compute='_compute_payment_terms_note', sanitize=False)
    user_can_invoicing = fields.Boolean(
        string="User Can Invoicing", compute='_compute_invoicing_permissions')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('invoice_number'):
                vals['invoice_number'] = self.env['ir.sequence'].next_by_code(
                    'sales.invoice'
                ) or '/'
        invoices = super(sales_invoice, self).create(vals_list)
        invoices._rebuild_journal_items()
        return invoices

    @api.depends('line_ids.sub_total', 'line_ids.tax_amount', 'line_ids.total')
    def _compute_amounts(self):
        for record in self:
            record.amount_untaxed = sum(record.line_ids.mapped('sub_total'))
            record.amount_tax = sum(record.line_ids.mapped('tax_amount'))
            record.amount_total = sum(record.line_ids.mapped('total'))

    @api.depends('payment_ids.state', 'payment_ids.amount', 'amount_total', 'state')
    def _compute_payment_state(self):
        for record in self:
            current_invoice_posted_payments = record.payment_ids.filtered(
                lambda payment: payment.state == 'posted'
            )
            if record.invoice_type == 'regular' and record.sales_order_id:
                related_invoices = record.sales_order_id.invoice_ids.filtered(
                    lambda invoice: invoice.state != 'cancel'
                )
                posted_payments = related_invoices.mapped('payment_ids').filtered(
                    lambda payment: payment.state == 'posted'
                )
            else:
                posted_payments = record.payment_ids.filtered(
                    lambda payment: payment.state == 'posted'
                )
            paid = sum(posted_payments.mapped('amount'))
            due = record.amount_total - paid
            record.amount_paid = paid
            record.amount_due = max(due, 0.0)
            record.payment_count = len(current_invoice_posted_payments)
            if record.invoice_type == 'regular':
                if paid <= 0:
                    record.payment_state = 'not_paid'
                elif due > 0:
                    record.payment_state = 'partial'
                else:
                    record.payment_state = 'paid'
            elif record.state != 'posted':
                record.payment_state = 'not_paid'
            elif paid <= 0:
                record.payment_state = 'not_paid'
            elif due > 0:
                record.payment_state = 'partial'
            else:
                record.payment_state = 'paid'

    @api.depends(
        'invoice_type',
        'sales_order_id',
        'sales_order_id.invoice_ids.state',
        'sales_order_id.invoice_ids.invoice_date',
        'sales_order_id.invoice_ids.payment_ids.state',
        'sales_order_id.invoice_ids.payment_ids.payment_date',
        'sales_order_id.invoice_ids.payment_ids.amount',
    )
    def _compute_previous_payments(self):
        for record in self:
            previous_payments = self.env['sales.payment']
            if record.invoice_type == 'regular' and record.sales_order_id:
                previous_invoices = record.sales_order_id.invoice_ids.filtered(
                    lambda invoice: invoice.id != record.id and invoice.state != 'cancel'
                )
                previous_payments = previous_invoices.mapped('payment_ids').filtered(
                    lambda payment: payment.state == 'posted'
                ).sorted(lambda payment: (payment.payment_date or fields.Date.today(), payment.id))
            record.previous_payment_ids = [(6, 0, previous_payments.ids)]
            record.previous_payment_count = len(previous_payments)

    @api.depends('payment_terms_id', 'invoice_date', 'amount_total')
    def _compute_payment_terms_note(self):
        for record in self:
            term = record.payment_terms_id
            if not term or not term.payment_terms_ids:
                record.payment_terms_note = ''
                continue

            baseline_date = record.invoice_date or fields.Date.today()
            lines = []
            lines.append(
                f"<div><b>Payment terms:</b> {term.sales_text}</div>"
            )

            term_lines = term.payment_terms_ids.sorted('no_of_days')
            remaining = record.amount_total
            total_terms = len(term_lines)

            for i, tline in enumerate(term_lines, start=1):
                if i == total_terms:
                    amount = remaining
                else:
                    amount = round(record.amount_total *
                                   (tline.percentage / 100.0), 0)
                    remaining -= amount

                due_date = baseline_date + timedelta(days=tline.no_of_days)
                formatted_amount = "Rp {:,.0f}".format(amount)
                formatted_date = due_date.strftime('%m/%d/%Y')
                lines.append(
                    f"<div><b>{i}#</b> Installment of <b>{formatted_amount}</b> "
                    f"due on <b style='color: #704A66;'>{formatted_date}</b></div>"
                )

            record.payment_terms_note = ''.join(lines)

    @api.depends('journal_item_ids')
    def _compute_journal_item_count(self):
        for record in self:
            record.journal_item_count = len(record.journal_item_ids)

    @api.depends('credit_note_ids')
    def _compute_credit_note_count(self):
        for record in self:
            record.credit_note_count = len(record.credit_note_ids)

    def write(self, vals):
        res = super(sales_invoice, self).write(vals)
        self._rebuild_journal_items()
        return res

    def _get_sign_multiplier(self):
        self.ensure_one()
        return -1 if self.document_type == 'credit_note' else 1

    def _get_due_date_from_term(self, term_line):
        self.ensure_one()
        baseline_date = self.invoice_date or fields.Date.today()
        payment_term = self.payment_terms_id
        if payment_term and payment_term.baseline_date == 'post' and self.posted_date:
            baseline_date = fields.Date.to_date(self.posted_date)
        return baseline_date + timedelta(days=term_line.no_of_days)

    def _prepare_receivable_journal_items(self, sequence):
        self.ensure_one()
        items = []
        sign = self._get_sign_multiplier()
        if self.payment_terms_id and self.payment_terms_id.payment_terms_ids:
            term_lines = self.payment_terms_id.payment_terms_ids.sorted(
                'no_of_days')
            remaining_amount = self.amount_total
            total_terms = len(term_lines)
            for index, term_line in enumerate(term_lines, start=1):
                if index == total_terms:
                    debit = remaining_amount
                else:
                    debit = round(self.amount_total *
                                  (term_line.percentage / 100.0), 0)
                    remaining_amount -= debit
                items.append({
                    'invoice_id': self.id,
                    'sequence': sequence,
                    'line_type': 'receivable',
                    'account_code': '110000',
                    'account_name': 'Account Receivable',
                    'label': self.invoice_number,
                    'partner_name': self.customer_id.customer_name,
                    'date_maturity': self._get_due_date_from_term(term_line),
                    'debit': debit if sign > 0 else 0.0,
                    'credit': 0.0 if sign > 0 else abs(debit),
                })
                sequence += 1
        else:
            items.append({
                'invoice_id': self.id,
                'sequence': sequence,
                'line_type': 'receivable',
                'account_code': '110000',
                'account_name': 'Account Receivable',
                'label': self.invoice_number,
                'partner_name': self.customer_id.customer_name,
                'date_maturity': self.invoice_date,
                'debit': self.amount_total if sign > 0 else 0.0,
                'credit': 0.0 if sign > 0 else abs(self.amount_total),
            })
            sequence += 1
        return items, sequence

    def _prepare_revenue_journal_items(self, sequence):
        self.ensure_one()
        items = []
        sign = self._get_sign_multiplier()
        for line in self.line_ids.sorted('sequence'):
            if not line.sub_total:
                continue
            items.append({
                'invoice_id': self.id,
                'sequence': sequence,
                'line_type': 'product',
                'account_code': '400000',
                'account_name': 'Sales Revenue',
                'label': line.description,
                'partner_name': self.customer_id.customer_name,
                'product_id': line.product_id.id,
                'debit': line.sub_total if sign < 0 else 0.0,
                'credit': line.sub_total if sign > 0 else 0.0,
            })
            sequence += 1
        return items, sequence

    def _prepare_tax_journal_items(self, sequence):
        self.ensure_one()
        items = []
        sign = self._get_sign_multiplier()
        grouped_taxes = {}
        for line in self.line_ids:
            if not line.tax_amount:
                continue
            tax_key = line.tax_id.id if line.tax_id else 0
            grouped_taxes.setdefault(tax_key, {
                'name': line.tax_id.name if line.tax_id else 'Tax',
                'amount': 0.0,
                'tax_id': line.tax_id.id if line.tax_id else False,
            })
            grouped_taxes[tax_key]['amount'] += line.tax_amount

        for tax_values in grouped_taxes.values():
            items.append({
                'invoice_id': self.id,
                'sequence': sequence,
                'line_type': 'tax',
                'account_code': '210000',
                'account_name': 'Tax Payable',
                'label': tax_values['name'],
                'partner_name': self.customer_id.customer_name,
                'tax_id': tax_values['tax_id'],
                'debit': tax_values['amount'] if sign < 0 else 0.0,
                'credit': tax_values['amount'] if sign > 0 else 0.0,
            })
            sequence += 1
        return items, sequence

    def _rebuild_journal_items(self):
        for invoice in self:
            invoice.journal_item_ids.unlink()
            if not invoice.line_ids:
                continue

            sequence = 1
            journal_items = []
            receivable_items, sequence = invoice._prepare_receivable_journal_items(
                sequence)
            revenue_items, sequence = invoice._prepare_revenue_journal_items(
                sequence)
            tax_items, sequence = invoice._prepare_tax_journal_items(sequence)
            journal_items.extend(receivable_items)
            journal_items.extend(revenue_items)
            journal_items.extend(tax_items)

            if journal_items:
                self.env['sales.invoice.journal.item'].create(journal_items)

    def action_post(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft invoices can be confirmed."))
        if not self.line_ids:
            raise UserError(
                _("Please add at least one invoice line before confirming this invoice."))
        self._rebuild_journal_items()

        self.write({
            'state': 'posted',
            'posted_date': fields.Datetime.now(),
        })
        return self.action_view_invoice()

    def action_cancel_invoice(self):
        self.ensure_one()
        if self.state == 'posted':
            raise UserError(_("Posted invoices cannot be cancelled."))
        self.state = 'cancel'
        return self.action_back_to_invoices()

    def action_set_to_draft(self):
        self.ensure_one()
        self._check_invoicing_access()
        if self.state not in ('cancel', 'posted'):
            raise UserError(
                _("Only cancelled or posted invoices can be reset to draft."))
        self.state = 'draft'
        return self.action_view_invoice()

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Invoice',
            'res_model': 'sales.invoice',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_open_sales_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sales.sales_order',
            'view_mode': 'form',
            'res_id': self.sales_order_id.id,
            'target': 'current',
        }

    def action_open_credit_note_wizard(self):
        self.ensure_one()
        self._check_invoicing_access()
        if self.state != 'posted':
            raise UserError(
                _("Credit note can only be created from a posted invoice."))
        if self.document_type != 'invoice':
            raise UserError(
                _("Credit note can only be created from a customer invoice."))
        return {
            'name': _('Credit Note'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.credit.note.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_credit_note_date': fields.Date.today(),
            },
        }

    def action_view_credit_notes(self):
        self.ensure_one()
        action = self.action_back_to_invoices()
        if len(self.credit_note_ids) > 1:
            action['domain'] = [('id', 'in', self.credit_note_ids.ids)]
        elif len(self.credit_note_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.credit_note_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _prepare_credit_note_vals(self, reason, credit_note_date):
        self.ensure_one()
        line_commands = []
        for line in self.line_ids.sorted('sequence'):
            line_commands.append((0, 0, {
                'sequence': line.sequence,
                'sales_order_line_id': line.sales_order_line_id.id,
                'product_id': line.product_id.id,
                'description': line.description,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'discount': line.discount,
                'tax_id': line.tax_id.id,
                'tax_percentage': line.tax_percentage,
                'source_subtotal': line.source_subtotal,
            }))

        return {
            'sales_order_id': self.sales_order_id.id,
            'customer_id': self.customer_id.id,
            'customer_address': self.customer_address,
            'document_type': 'credit_note',
            'sales_name': self.sales_name.id,
            'delivery_date': self.delivery_date,
            'payment_terms_id': self.payment_terms_id.id,
            'invoice_type': self.invoice_type,
            'invoice_date': credit_note_date,
            'order_date': self.order_date,
            'source_invoice_id': self.id,
            'credit_note_reason': reason,
            'percentage': self.percentage,
            'fixed_amount': self.fixed_amount,
            'line_ids': line_commands,
        }

    def action_create_credit_note(self, reason, credit_note_date):
        self.ensure_one()
        self._check_invoicing_access()
        if self.state != 'posted':
            raise UserError(
                _("Credit note can only be created from a posted invoice."))
        if self.document_type != 'invoice':
            raise UserError(
                _("Credit note can only be created from a customer invoice."))
        credit_note = self.create(
            self._prepare_credit_note_vals(reason, credit_note_date))
        return credit_note.action_view_invoice()

    def action_register_payment(self):
        self.ensure_one()
        self._check_invoicing_access()
        if self.state != 'posted':
            raise UserError(
                _("Payment can only be registered for posted invoices."))
        if self.payment_state == 'paid':
            raise UserError(_("This invoice is already fully paid."))
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.register.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
            },
        }

    def action_send_invoice_by_email(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_("Only posted invoices can be sent by email."))

        template = self.env.ref(
            'sales.email_template_sales_invoice', raise_if_not_found=False)

        # Generate PDF dan simpan sebagai attachment
        attachment_ids = []
        try:
            pdf_content, _mime = self.env['ir.actions.report']._render_qweb_pdf(
                'sales.action_report_sales_invoice', [self.id])
            filename = 'Invoice - %s.pdf' % self.invoice_number
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            attachment_ids = [attachment.id]
        except Exception:
            pass

        # Tentukan email_from yang valid dengan urutan prioritas:
        # 1. Email login salesperson (user_id.email atau login)
        # 2. Email user yang sedang login
        # 3. Email company
        email_from = False
        if self.sales_name and self.sales_name.user_id:
            sp_user = self.sales_name.user_id
            email_from = sp_user.email or sp_user.login or False
        if not email_from:
            current_user = self.env.user
            email_from = current_user.email or current_user.login or False
        if not email_from:
            email_from = self.env.company.email or False

        if not email_from:
            raise UserError(_(
                "Tidak dapat mengirim email: alamat email pengirim belum dikonfigurasi. "
                "Harap isi email pada profil salesperson, akun pengguna Anda, atau email perusahaan."
            ))

        ctx = {
            'default_model': 'sales.invoice',
            'default_res_ids': [self.id],
            'default_use_template': bool(template),
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'default_attachment_ids': [(6, 0, attachment_ids)],
            'default_customer_ids': [(6, 0, [self.customer_id.id])] if self.customer_id else [],
            'default_email_from': email_from,
            'redirect_to_tree': 'sales.sales_invoice_action',
            'show_email_in_wizard': True,
        }

        # Sync email ke partner jika belum sesuai
        partner = self.customer_id.partner_id
        if partner and self.customer_id.email and partner.email != self.customer_id.email:
            partner.sudo().write({'email': self.customer_id.email})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Invoice by Email'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def action_view_payments(self):
        self.ensure_one()
        posted = self.payment_ids.filtered(lambda p: p.state == 'posted')
        if len(posted) == 1:
            return posted.action_view_payment()
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.payment',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id), ('state', '=', 'posted')],
            'target': 'current',
        }

    def action_back_to_invoices(self):
        self.ensure_one()
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'sales.invoice',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'context': self.env.context,
        }

    def _compute_invoicing_permissions(self):
        self.user_can_invoicing = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_invoicing = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        invoicing_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'sales_order'),
            ('can_invoicing', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if invoicing_authorized:
            for rec in self:
                rec.user_can_invoicing = True

    def _check_invoicing_access(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        invoicing_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'sales_order'),
            ('can_invoicing', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)
        if not invoicing_authorized:
            raise UserError(
                _("You do not have access rights to perform invoicing actions."))


class sales_invoice_line(models.Model):
    _name = 'sales.invoice.line'
    _description = 'Sales Invoice Line'
    _order = 'sequence, id'

    invoice_id = fields.Many2one(
        comodel_name='sales.invoice', string='Invoice', ondelete='cascade', index=True, required=True)
    sequence = fields.Integer(string="Sequence", default=1)
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], string='Display Type', default=False)
    sales_order_line_id = fields.Many2one(
        comodel_name='sales.sales_order_line', string='Sales Order Line', ondelete='set null', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product', ondelete='set null', index=True)
    description = fields.Char(string="Description", required=True)
    quantity = fields.Float(string="Quantity", default=1)
    unit_price = fields.Float(string="Unit Price", digits=(16, 0), default=0.0)
    discount = fields.Float(string="Discount (%)", default=0.0)
    tax_id = fields.Many2one(
        comodel_name='sales.taxes', string='Tax', ondelete='set null', index=True)
    tax_percentage = fields.Float(
        string="Tax Percentage", digits=(16, 2), default=0.0)
    source_subtotal = fields.Float(
        string="Source Untaxed Amount", digits=(16, 0), default=0.0)
    sub_total = fields.Float(
        string="Sub Total", compute='_compute_amounts', store=True, digits=(16, 0))
    tax_amount = fields.Float(
        string="Tax Amount", compute='_compute_amounts', store=True, digits=(16, 0))
    total = fields.Float(
        string="Total", compute='_compute_amounts', store=True, digits=(16, 0))

    @api.depends('quantity', 'unit_price', 'discount', 'tax_percentage')
    def _compute_amounts(self):
        for record in self:
            if record.display_type:
                record.sub_total = 0.0
                record.tax_amount = 0.0
                record.total = 0.0
                continue
            record.sub_total = record.quantity * \
                record.unit_price * (1 - record.discount / 100.0)
            record.tax_amount = record.sub_total * \
                (record.tax_percentage / 100.0)
            record.total = record.sub_total + record.tax_amount

    @api.onchange('tax_id')
    def _onchange_tax_id(self):
        for record in self:
            record.tax_percentage = record.tax_id.tax_percentage if record.tax_id else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('display_type'):
                vals.update({
                    'product_id': False,
                    'sales_order_line_id': False,
                    'quantity': 0.0,
                    'unit_price': 0.0,
                    'discount': 0.0,
                    'tax_id': False,
                    'tax_percentage': 0.0,
                    'source_subtotal': 0.0,
                })
        lines = super(sales_invoice_line, self).create(vals_list)
        lines.mapped('invoice_id')._rebuild_journal_items()
        return lines

    def write(self, vals):
        if vals.get('display_type'):
            vals.update({
                'product_id': False,
                'sales_order_line_id': False,
                'quantity': 0.0,
                'unit_price': 0.0,
                'discount': 0.0,
                'tax_id': False,
                'tax_percentage': 0.0,
                'source_subtotal': 0.0,
            })
        res = super(sales_invoice_line, self).write(vals)
        self.mapped('invoice_id')._rebuild_journal_items()
        return res

    def unlink(self):
        invoices = self.mapped('invoice_id')
        res = super(sales_invoice_line, self).unlink()
        invoices._rebuild_journal_items()
        return res


class sales_invoice_journal_item(models.Model):
    _name = 'sales.invoice.journal.item'
    _description = 'Sales Invoice Journal Item'
    _order = 'sequence, id'

    invoice_id = fields.Many2one(
        comodel_name='sales.invoice', string='Invoice', ondelete='cascade', index=True, required=True)
    sequence = fields.Integer(string="Sequence", default=1)
    line_type = fields.Selection([
        ('receivable', 'Receivable'),
        ('product', 'Product'),
        ('tax', 'Tax')
    ], string="Line Type", default='product')
    account_code = fields.Char(string="Account Code")
    account_name = fields.Char(string="Account")
    label = fields.Char(string="Label")
    partner_name = fields.Char(string="Partner")
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product', ondelete='set null', index=True)
    tax_id = fields.Many2one(
        comodel_name='sales.taxes', string='Tax', ondelete='set null', index=True)
    date_maturity = fields.Date(string="Due Date")
    debit = fields.Float(string="Debit", digits=(16, 0), default=0.0)
    credit = fields.Float(string="Credit", digits=(16, 0), default=0.0)


class sales_create_invoice_wizard(models.TransientModel):
    _name = 'sales.create.invoice.wizard'
    _description = 'Create Sales Invoice Wizard'

    sales_order_id = fields.Many2one(
        comodel_name='sales.sales_order', string='Sales Order', required=True, readonly=True)
    invoice_type = fields.Selection([
        ('regular', 'Regular Invoice'),
        ('down_payment_percentage', 'Down Payment (Percentage)'),
        ('down_payment_fixed', 'Down Payment (Fixed Amount)')
    ], string="Create Invoice", default='regular', required=True)
    already_invoiced_count = fields.Integer(
        string="Already Invoiced", compute='_compute_invoice_history')
    already_invoiced_amount = fields.Float(
        string="Already Invoiced Amount", digits=(16, 0),
        compute='_compute_invoice_history')
    percentage = fields.Float(string="Down Payment Percentage", default=0.0)
    fixed_amount = fields.Float(
        string="Down Payment Amount", digits=(16, 0), default=0.0)

    @api.depends(
        'sales_order_id',
        'sales_order_id.invoice_ids.state',
        'sales_order_id.invoice_ids.amount_total',
    )
    def _compute_invoice_history(self):
        for record in self:
            active_invoices = record.sales_order_id.invoice_ids.filtered(
                lambda invoice: invoice.state != 'cancel'
            )
            record.already_invoiced_count = len(active_invoices)
            record.already_invoiced_amount = sum(
                active_invoices.mapped('amount_total'))

    def action_create_invoice(self):
        self.ensure_one()
        self.sales_order_id._check_invoicing_access()
        if self.invoice_type == 'down_payment_percentage' and self.percentage <= 0:
            raise UserError(
                _("Down payment percentage must be greater than zero."))
        if self.invoice_type == 'down_payment_fixed' and self.fixed_amount <= 0:
            raise UserError(
                _("Down payment fixed amount must be greater than zero."))

        invoice = self.sales_order_id.create_custom_invoice(
            self.invoice_type,
            percentage=self.percentage,
            fixed_amount=self.fixed_amount,
        )
        return invoice.action_view_invoice()


class sales_credit_note_wizard(models.TransientModel):
    _name = 'sales.credit.note.wizard'
    _description = 'Sales Credit Note Wizard'

    invoice_id = fields.Many2one(
        comodel_name='sales.invoice', string='Invoice', required=True, readonly=True)
    credit_note_date = fields.Date(
        string='Credit Note Date', default=fields.Date.today, required=True)
    reason = fields.Char(string='Reason displayed on Credit Note')

    def action_create_credit_note(self):
        self.ensure_one()
        return self.invoice_id.action_create_credit_note(
            self.reason,
            self.credit_note_date,
        )


# ─────────────────────────────────────────────
#  PAYMENT
# ─────────────────────────────────────────────

class sales_payment(models.Model):
    _name = 'sales.payment'
    _description = 'Sales Payment'
    _rec_name = 'payment_number'
    _order = 'payment_date desc, id desc'

    payment_number = fields.Char(
        string="Payment Number", readonly=True, copy=False)
    invoice_id = fields.Many2one(
        comodel_name='sales.invoice', string='Invoice',
        ondelete='restrict', index=True, required=True)
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer',
        ondelete='restrict', index=True, required=True)
    payment_date = fields.Date(
        string="Payment Date", required=True, default=fields.Date.today)
    payment_method = fields.Selection([
        ('manual', 'Manual'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('cash', 'Cash'),
    ], string="Payment Method", required=True, default='manual')
    memo = fields.Char(string="Memo / Reference")
    amount = fields.Float(string="Amount", digits=(16, 0), required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', readonly=True)
    currency = fields.Char(string="Currency", default='IDR')
    journal_item_ids = fields.One2many(
        'sales.payment.journal.item', 'payment_id', string='Journal Items')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('payment_number'):
                vals['payment_number'] = self.env['ir.sequence'].next_by_code(
                    'sales.payment') or '/'
        return super(sales_payment, self).create(vals_list)

    def _build_journal_items(self):
        """Create debit (cash/bank) and credit (receivable) journal entries."""
        for payment in self:
            payment.journal_item_ids.unlink()
            sign = 1  # receipt: debit cash, credit receivable
            payment.env['sales.payment.journal.item'].create([
                {
                    'payment_id': payment.id,
                    'sequence': 1,
                    'line_type': 'liquidity',
                    'account_code': '100000',
                    'account_name': 'Cash / Bank',
                    'label': payment.memo or payment.payment_number,
                    'partner_name': payment.customer_id.customer_name,
                    'debit': payment.amount * sign,
                    'credit': 0.0,
                },
                {
                    'payment_id': payment.id,
                    'sequence': 2,
                    'line_type': 'receivable',
                    'account_code': '110000',
                    'account_name': 'Account Receivable',
                    'label': payment.invoice_id.invoice_number,
                    'partner_name': payment.customer_id.customer_name,
                    'debit': 0.0,
                    'credit': payment.amount * sign,
                },
            ])

    def action_post(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft payments can be confirmed."))
        self._build_journal_items()
        self.write({'state': 'posted'})
        # Update invoice payment_state
        self.invoice_id._compute_payment_state()
        return self.action_view_payment()

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'posted':
            raise UserError(
                _("Posted payments cannot be cancelled directly. Reset to draft first."))
        self.write({'state': 'cancel'})
        self.invoice_id._compute_payment_state()
        return self.action_view_payment()

    def action_reset_to_draft(self):
        self.ensure_one()
        self.journal_item_ids.unlink()
        self.write({'state': 'draft'})
        self.invoice_id._compute_payment_state()
        return self.action_view_payment()

    def action_view_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment',
            'res_model': 'sales.payment',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_open_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'sales.invoice',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }


class sales_payment_journal_item(models.Model):
    _name = 'sales.payment.journal.item'
    _description = 'Sales Payment Journal Item'
    _order = 'sequence, id'

    payment_id = fields.Many2one(
        comodel_name='sales.payment', string='Payment',
        ondelete='cascade', index=True, required=True)
    sequence = fields.Integer(string="Sequence", default=1)
    line_type = fields.Selection([
        ('liquidity', 'Liquidity'),
        ('receivable', 'Receivable'),
    ], string="Line Type", default='liquidity')
    account_code = fields.Char(string="Account Code")
    account_name = fields.Char(string="Account")
    label = fields.Char(string="Label")
    partner_name = fields.Char(string="Partner")
    debit = fields.Float(string="Debit", digits=(16, 0), default=0.0)
    credit = fields.Float(string="Credit", digits=(16, 0), default=0.0)


class sales_register_payment_wizard(models.TransientModel):
    _name = 'sales.register.payment.wizard'
    _description = 'Register Payment Wizard'

    invoice_id = fields.Many2one(
        comodel_name='sales.invoice', string='Invoice',
        required=True, readonly=True)
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer', readonly=True)
    invoice_number = fields.Char(string="Invoice", readonly=True)
    payment_date = fields.Date(
        string="Payment Date", required=True, default=fields.Date.today)
    payment_method = fields.Selection([
        ('manual', 'Manual'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('cash', 'Cash'),
    ], string="Payment Method", required=True, default='manual')
    memo = fields.Char(string="Memo")
    amount = fields.Float(string="Amount", digits=(16, 0), required=True)
    amount_due = fields.Float(
        string="Amount Due", digits=(16, 0), readonly=True)
    currency = fields.Char(string="Currency", default='IDR', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        invoice_id = self.env.context.get('default_invoice_id')
        if invoice_id:
            invoice = self.env['sales.invoice'].browse(invoice_id)
            res.update({
                'invoice_id': invoice.id,
                'customer_id': invoice.customer_id.id,
                'invoice_number': invoice.invoice_number,
                'amount': invoice.amount_due,
                'amount_due': invoice.amount_due,
                'memo': invoice.invoice_number,
            })
        return res

    def action_register_payment(self):
        self.ensure_one()
        self.invoice_id._check_invoicing_access()
        if self.amount <= 0:
            raise UserError(_("Payment amount must be greater than zero."))
        if self.amount > self.amount_due:
            raise UserError(_("Payment amount cannot exceed the amount due (%(due)s).") % {
                'due': '{:,.0f}'.format(self.amount_due)
            })

        payment = self.env['sales.payment'].create({
            'invoice_id': self.invoice_id.id,
            'customer_id': self.customer_id.id,
            'payment_date': self.payment_date,
            'payment_method': self.payment_method,
            'memo': self.memo,
            'amount': self.amount,
            'currency': self.currency,
        })
        payment.action_post()
        return payment.action_view_payment()


# ─────────────────────────────────────────────
#  SALES DELIVERY (mirroring purchases.receipt)
# ─────────────────────────────────────────────

class SalesDelivery(models.Model):
    _name = 'sales.delivery'
    _inherit = ['navigation.mixin']
    _description = 'Sales Deliveries'
    _rec_name = 'delivery_number'
    _order = 'delivery_number desc, id desc'
    _menu_code = 'sales_deliveries'

    delivery_number = fields.Char(
        string="Delivery Number", readonly=True, copy=False)
    sales_order_id = fields.Many2one(
        comodel_name='sales.sales_order', string='Sales Order',
        ondelete='restrict', index=True, required=True)
    customer_id = fields.Many2one(
        comodel_name='sales.customer', string='Customer',
        ondelete='restrict', index=True, required=True)
    delivery_date = fields.Date(
        string="Delivery Date", default=fields.Date.today, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    done_date = fields.Datetime(
        string="Done On", readonly=True, copy=False)
    line_ids = fields.One2many(
        'sales.delivery.line', 'delivery_id', string='Delivery Lines')
    note = fields.Text(string="Notes")
    is_edit = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('delivery_number'):
                vals['delivery_number'] = self.env['ir.sequence'].next_by_code(
                    'sales.delivery') or '/'
        return super().create(vals_list)

    def unlink(self):
        if any(d.state == 'done' for d in self):
            raise UserError(_("Done deliveries cannot be deleted."))
        return super().unlink()

    def action_done(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft deliveries can be validated."))
        self.write({
            'state': 'done',
            'done_date': fields.Datetime.now(),
        })

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_("Done deliveries cannot be cancelled."))
        self.state = 'cancel'

    def action_view_delivery(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery'),
            'res_model': 'sales.delivery',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_open_sales_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sales.sales_order',
            'view_mode': 'form',
            'res_id': self.sales_order_id.id,
            'target': 'current',
        }


class SalesDeliveryLine(models.Model):
    _name = 'sales.delivery.line'
    _description = 'Sales Delivery Line'
    _order = 'id'

    delivery_id = fields.Many2one(
        comodel_name='sales.delivery', string='Delivery',
        ondelete='cascade', index=True, required=True)
    sales_order_line_id = fields.Many2one(
        comodel_name='sales.sales_order_line', string='SO Line',
        ondelete='set null', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product',
        ondelete='set null', index=True)
    description = fields.Char(string="Description", required=True)
    ordered_qty = fields.Float(
        string="Ordered Qty", digits=(16, 2), readonly=True)
    quantity = fields.Float(string="Delivered Qty", digits=(16, 2), default=0.0)
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM")

    @api.onchange('sales_order_line_id')
    def _onchange_sales_order_line_id(self):
        if self.sales_order_line_id:
            self.product_id = self.sales_order_line_id.product_id
            if self.sales_order_line_id.product_id:
                self.description = self.sales_order_line_id.product_id.product_name
            self.ordered_qty = self.sales_order_line_id.quantity
            self.quantity = self.sales_order_line_id.qty_to_deliver
