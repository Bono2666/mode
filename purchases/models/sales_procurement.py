from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SalesProductsVendor(models.Model):
    _inherit = 'sales.products'

    vendor_id = fields.Many2one(
        comodel_name='purchases.vendor', string='Vendor',
        ondelete='set null', index=True)


class PurchaseOrderSalesLink(models.Model):
    _inherit = 'purchases.purchase_order'

    sales_order_id = fields.Many2one(
        comodel_name='sales.sales_order', string='Sales Order',
        ondelete='set null', index=True, copy=False)
    sales_order_ids = fields.Many2many(
        comodel_name='sales.sales_order',
        relation='purchases_purchase_order_sales_order_rel',
        column1='purchase_order_id',
        column2='sales_order_id',
        string='Sales Orders', copy=False)
    sales_order_code = fields.Char(
        related='sales_order_id.sales_code', string='Sales Order Code',
        store=True, readonly=True)
    based_on_so = fields.Char(
        string='Base On', compute='_compute_based_on_so', store=True)
    based_on_so_links = fields.Json(
        string='Based On Links', compute='_compute_based_on_so')

    def _purchase_return_context(self):
        """Context untuk buka SO / kembali ke PO atau RFQ yang sama."""
        self.ensure_one()
        ctx = {
            'return_purchase_order_id': self.id,
        }
        if self.entry_menu_code:
            ctx['access_menu_code'] = self.entry_menu_code
            ctx['default_entry_menu_code'] = self.entry_menu_code
        return ctx

    @api.depends('sales_order_ids', 'sales_order_ids.sales_code', 'sales_order_id.sales_code')
    def _compute_based_on_so(self):
        for order in self:
            sales_orders = order.sales_order_ids
            if not sales_orders and order.sales_order_id:
                sales_orders = order.sales_order_id
            codes = [c for c in sales_orders.sorted('sales_code').mapped('sales_code') if c]
            if codes:
                order.based_on_so = _('Based On %s') % ', '.join(codes)
            else:
                order.based_on_so = False
            order.based_on_so_links = [
                {'id': so.id, 'code': so.sales_code or ''}
                for so in sales_orders.sorted('sales_code')
            ] if sales_orders else False

    def _link_sales_order(self, sales_order):
        """Tambahkan SO ke daftar Based On pada PO/RFQ ini."""
        self.ensure_one()
        if not sales_order:
            return
        vals = {}
        if sales_order not in self.sales_order_ids:
            vals['sales_order_ids'] = [(4, sales_order.id)]
        if not self.sales_order_id:
            vals['sales_order_id'] = sales_order.id
        if vals:
            self.write(vals)

    def init(self):
        """Isi relasi M2M dari sales_order_id lama (setelah upgrade modul)."""
        self.env.cr.execute("""
            INSERT INTO purchases_purchase_order_sales_order_rel
                (purchase_order_id, sales_order_id)
            SELECT po.id, po.sales_order_id
            FROM purchases_purchase_order po
            WHERE po.sales_order_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM purchases_purchase_order_sales_order_rel rel
                WHERE rel.purchase_order_id = po.id
                  AND rel.sales_order_id = po.sales_order_id
            )
        """)

    def action_open_sales_order(self):
        """Buka SO tertentu (gunakan context open_sales_order_id jika ada)."""
        self.ensure_one()
        so_id = self.env.context.get('open_sales_order_id')
        sales_order = self.env['sales.sales_order'].browse(so_id) if so_id else (
            self.sales_order_id or self.sales_order_ids[:1])
        if not sales_order:
            return False
        action = sales_order.get_formview_action()
        action['name'] = _('Sales Order')
        action['context'] = {
            **action.get('context', {}),
            **self._purchase_return_context(),
        }
        return action


class SalesOrderProcurement(models.Model):
    _inherit = 'sales.sales_order'

    def name_get(self):
        if self.env.context.get('from_purchase_based_on'):
            return [
                (so.id, _('Based On %s') % (so.sales_code or ''))
                for so in self
            ]
        return super().name_get()

    def get_formview_action(self, access_uid=None):
        """Saat SO dibuka dari form PO, bawa context agar tombol Back kembali ke PO."""
        action = super().get_formview_action(access_uid=access_uid)
        if self.env.context.get('active_model') == 'purchases.purchase_order':
            po_id = self.env.context.get('active_id')
            if po_id:
                ctx = dict(action.get('context', {}))
                ctx['return_purchase_order_id'] = po_id
                action['context'] = ctx
        return action

    purchase_order_ids = fields.Many2many(
        'purchases.purchase_order',
        relation='purchases_purchase_order_sales_order_rel',
        column1='sales_order_id',
        column2='purchase_order_id',
        string='Related RFQs')

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_procurement_rfq()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if res and ('order_line_ids' in vals or 'state' in vals):
            self._sync_procurement_rfq()
        return res

    def action_back_to_purchase_order(self):
        self.ensure_one()
        po_id = self.env.context.get('return_purchase_order_id')
        if not po_id:
            return self.action_back_to_sales()
        po = self.env['purchases.purchase_order'].browse(po_id)
        if not po.exists():
            return self.action_back_to_sales()
        return po.action_view_purchase_order()

    def _sync_procurement_rfq(self):
        """Sinkronkan RFQ dengan kekurangan stok saat SO dibuat/diupdate."""
        missing_vendor_products = []
        po_ctx = {'skip_purchase_order_create_auth_check': True}

        for order in self.filtered(lambda o: o.state != 'cancel'):
            shortages = order._get_shortage_product_quantities()
            linked_rfqs = order.purchase_order_ids.filtered(
                lambda p: p.state in ('draft', 'sent'))

            for rfq in linked_rfqs:
                for line in rfq.order_line_ids:
                    product = line.product_id
                    if not product:
                        continue
                    if product in shortages:
                        line.write({'quantity': float(shortages[product])})
                    else:
                        line.unlink()

            for product, qty in shortages.items():
                if not product.vendor_id:
                    missing_vendor_products.append(product.product_name)
                    continue
                if linked_rfqs.filtered(
                        lambda r: product in r.order_line_ids.product_id):
                    continue
                rfq = order._find_active_rfq_for_product(product)
                if rfq:
                    order._set_rfq_line_qty(rfq, product, qty)
                else:
                    order.with_context(**po_ctx)._create_rfq_for_product(
                        product, qty)

        if missing_vendor_products:
            raise UserError(_(
                "Cannot create RFQ automatically. The following products have "
                "insufficient stock but no vendor configured:\n%(products)s"
            ) % {'products': '\n'.join(f"- {name}" for name in missing_vendor_products)})

    def _get_shortage_product_quantities(self):
        """Kekurangan per produk: kebutuhan SO vs stok fisik dikurangi booking SO lain."""
        self.ensure_one()
        need_per_product = {}
        for line in self.order_line_ids:
            if not line.product_id:
                continue
            p = line.product_id
            need_per_product[p] = need_per_product.get(p, 0) + line.quantity

        if not need_per_product:
            return {}

        products = self.env['sales.products'].browse(
            [p.id for p in need_per_product])
        products.invalidate_recordset(['qty_reserved_sale'])

        product_qty = {}
        for product, need in need_per_product.items():
            r_all = product.qty_reserved_sale
            r_other = r_all - need
            available = product.stock - r_other
            shortage = max(0, need - available)
            if shortage > 0:
                product_qty[product] = shortage
        return product_qty

    def _find_active_rfq_for_product(self, product):
        self.ensure_one()
        rfq = self.env['purchases.purchase_order'].search([
            ('sales_order_ids', 'in', self.id),
            ('state', 'in', ['draft', 'sent']),
            ('order_line_ids.product_id', '=', product.id),
        ], order='id desc', limit=1)
        if rfq:
            return rfq
        return self.env['purchases.purchase_order'].search([
            ('state', 'in', ['draft', 'sent']),
            ('order_line_ids.product_id', '=', product.id),
        ], order='id desc', limit=1)

    def _prepare_rfq_line_vals(self, product, quantity):
        default_tax = self.env['sales.taxes'].sudo().search(
            [('default_tax', '=', True)], limit=1)
        return {
            'product_id': product.id,
            'description': product.product_name,
            'quantity': float(quantity),
            'unit_price': product.price,
            'taxes': default_tax.id if default_tax else False,
        }

    def _set_rfq_line_qty(self, rfq, product, quantity):
        self.ensure_one()
        rfq._link_sales_order(self)
        line = rfq.order_line_ids.filtered(lambda l: l.product_id == product)
        if line:
            line.write({'quantity': float(quantity)})
        else:
            rfq.write({
                'order_line_ids': [
                    (0, 0, self._prepare_rfq_line_vals(product, quantity))],
            })

    def _create_rfq_for_product(self, product, quantity):
        self.ensure_one()
        vendor = product.vendor_id
        rfq = self.env['purchases.purchase_order'].create({
            'vendor_id': vendor.id,
            'entry_menu_code': 'rfq',
            'state': 'draft',
            'sales_order_id': self.id,
            'sales_order_ids': [(6, 0, [self.id])],
            'payment_terms': vendor.payment_terms.id if vendor.payment_terms else False,
            'order_line_ids': [(0, 0, self._prepare_rfq_line_vals(product, quantity))],
        })
        return rfq


class SalesOrderLineProcurement(models.Model):
    _inherit = 'sales.sales_order_line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.mapped('sales_order_id')._sync_procurement_rfq()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'product_id', 'quantity'} & set(vals.keys()):
            self.mapped('sales_order_id')._sync_procurement_rfq()
        return res
