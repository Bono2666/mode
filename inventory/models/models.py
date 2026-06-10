from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class InventoryAccessMixin(models.AbstractModel):
    _name = 'inventory.access.mixin'
    _description = 'Inventory Access Mixin'

    user_can_create = fields.Boolean(
        compute='_compute_custom_permissions', store=False)
    user_can_update = fields.Boolean(
        compute='_compute_custom_permissions', store=False)
    user_can_delete = fields.Boolean(
        compute='_compute_custom_permissions', store=False)
    user_can_confirm = fields.Boolean(
        compute='_compute_custom_permissions', store=False)
    model_description = fields.Char(compute='_compute_model_description')

    def _compute_model_description(self):
        for record in self:
            record.model_description = self._description

    @api.model
    def _get_custom_access(self):
        if self.env.user.has_group('base.group_system'):
            return True
        menu_code = getattr(self, '_menu_code', False)
        if not menu_code:
            return False
        return self.env['general.auth'].sudo().search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', menu_code),
        ], limit=1)

    @api.model
    def _check_custom_access(self, permission, message):
        access = self._get_custom_access()
        if access is True:
            return
        if not access or not getattr(access, permission, False):
            raise UserError(message)

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)
        access = self._get_custom_access()
        can_create = access is True or bool(access and access.can_create)
        if not can_create:
            import lxml.etree as etree
            for view_type in ['list', 'tree', 'form']:
                if view_type in res.get('views', {}):
                    doc = etree.fromstring(res['views'][view_type]['arch'])
                    doc.set('create', '0')
                    res['views'][view_type]['arch'] = etree.tostring(
                        doc, encoding='unicode')
        return res

    @api.depends_context('uid')
    def _compute_custom_permissions(self):
        access = self._get_custom_access()
        for record in self:
            if access is True:
                record.user_can_create = True
                record.user_can_update = True
                record.user_can_delete = True
                record.user_can_confirm = True
            elif access:
                record.user_can_create = access.can_create
                record.user_can_update = access.can_update
                record.user_can_delete = access.can_delete
                record.user_can_confirm = access.can_confirm
            else:
                record.user_can_create = False
                record.user_can_update = False
                record.user_can_delete = False
                record.user_can_confirm = False

    def action_edit(self):
        self.ensure_one()
        self._check_custom_access(
            'can_update', _("You do not have access rights to edit this record."))
        self.write({'is_edit': True})
        return self._open_form()

    def action_save(self):
        self.ensure_one()
        self.write({'is_edit': False})
        return self._open_form()

    def action_delete(self):
        self.ensure_one()
        self._check_custom_access(
            'can_delete', _("You do not have access rights to delete this record."))
        action = self._back_action()
        self.unlink()
        return action

    def _open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_cancel_edit(self):
        """Discard edit mode and reset is_edit flag without access check."""
        self.ensure_one()
        self.with_context(skip_inventory_access=True).write({'is_edit': False})
        return self._open_form()

    def _back_action(self):
        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'tree,form',
            'target': 'main',
            'context': self.env.context,
        }

    def action_back(self):
        self.ensure_one()
        return self._back_action()


class Warehouse(models.Model):
    _name = 'inventory.warehouse'
    _inherit = ['inventory.access.mixin']
    _description = 'Warehouses'
    _rec_name = 'name'
    _menu_code = 'inventory_warehouses'

    code = fields.Char(string="Warehouse Code", readonly=True, copy=False)
    name = fields.Char(string="Warehouse Name", required=True)
    address = fields.Text(string="Address")
    active = fields.Boolean(default=True)
    location_ids = fields.One2many(
        'inventory.location', 'warehouse_id', string="Locations")
    is_edit = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_custom_access(
            'can_create', _("You do not have access rights to create warehouses."))
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'inventory.warehouse') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_update', _("You do not have access rights to update warehouses."))
        return super().write(vals)

    def unlink(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to delete warehouses."))
        if self.env['inventory.stock_move'].search_count([
            '|', ('source_location_id.warehouse_id', 'in', self.ids),
            ('destination_location_id.warehouse_id', 'in', self.ids),
        ]):
            raise UserError(
                _("You cannot delete a warehouse that already has stock moves."))
        return super().unlink()


class Location(models.Model):
    _name = 'inventory.location'
    _inherit = ['inventory.access.mixin']
    _description = 'Locations'
    _rec_name = 'complete_name'
    _menu_code = 'inventory_locations'

    name = fields.Char(string="Location Name", required=True)
    warehouse_id = fields.Many2one(
        'inventory.warehouse', string="Warehouse", ondelete='cascade')
    usage = fields.Selection([
        ('internal', 'Internal'),
        ('supplier', 'Vendor Location'),
        ('customer', 'Customer Location'),
        ('inventory', 'Inventory Adjustment'),
        ('transit', 'Transit'),
    ], string="Location Type", default='internal', required=True)
    active = fields.Boolean(default=True)
    is_edit = fields.Boolean(default=False)

    @api.depends('name', 'warehouse_id.name')
    def _compute_complete_name(self):
        for record in self:
            if record.warehouse_id:
                record.complete_name = "%s/%s" % (
                    record.warehouse_id.name, record.name)
            else:
                record.complete_name = record.name

    complete_name = fields.Char(compute='_compute_complete_name', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_create', _("You do not have access rights to create locations."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_update', _("You do not have access rights to update locations."))
        return super().write(vals)

    def unlink(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to delete locations."))
        if self.env['inventory.stock_move'].search_count([
            '|', ('source_location_id', 'in', self.ids),
            ('destination_location_id', 'in', self.ids),
        ]):
            raise UserError(
                _("You cannot delete a location that already has stock moves."))
        return super().unlink()


class StockMove(models.Model):
    _name = 'inventory.stock_move'
    _inherit = ['inventory.access.mixin']
    _description = 'Stock Moves'
    _rec_name = 'move_number'
    _order = 'date desc, id desc'
    _menu_code = 'inventory_stock_moves'

    move_number = fields.Char(string="Move Number", readonly=True, copy=False)
    date = fields.Datetime(
        string="Date", default=fields.Datetime.now, required=True)
    product_id = fields.Many2one(
        'sales.products', string="Product", required=True, ondelete='restrict')
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM", readonly=True)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    source_location_id = fields.Many2one(
        'inventory.location', string="Source Location", ondelete='restrict')
    destination_location_id = fields.Many2one(
        'inventory.location', string="Destination Location", ondelete='restrict')
    move_type = fields.Selection([
        ('incoming', 'Receipt'),
        ('outgoing', 'Delivery'),
        ('internal', 'Internal Transfer'),
        ('adjustment', 'Adjustment'),
    ], string="Operation Type", required=True, default='internal')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    origin = fields.Char(string="Source Document")
    origin_model = fields.Char(string="Source Model", readonly=True)
    origin_id = fields.Integer(string="Source Record ID", readonly=True)
    origin_line_id = fields.Integer(string="Source Line ID", readonly=True)
    note = fields.Text(string="Notes")
    is_edit = fields.Boolean(default=False)

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_create', _("You do not have access rights to create stock moves."))
        for vals in vals_list:
            if not vals.get('move_number'):
                vals['move_number'] = self.env['ir.sequence'].next_by_code(
                    'inventory.stock_move') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_update', _("You do not have access rights to update stock moves."))
        return super().write(vals)

    def unlink(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to delete stock moves."))
        if any(move.state == 'done' for move in self):
            raise UserError(_("Done stock moves cannot be deleted."))
        return super().unlink()

    def action_done(self):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_confirm', _("You do not have access rights to validate stock moves."))
        for move in self:
            if move.state != 'draft':
                raise UserError(_("Only draft stock moves can be validated."))
            move._apply_product_stock()
            move.with_context(skip_inventory_access=True).write({
                'state': 'done',
                'date': fields.Datetime.now(),
                'is_edit': False,
            })
        return True

    def action_cancel(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to cancel stock moves."))
        for move in self:
            if move.state == 'done':
                raise UserError(_("Done stock moves cannot be cancelled."))
            move.with_context(skip_inventory_access=True).write({
                'state': 'cancel',
                'is_edit': False,
            })
        return True

    def _apply_product_stock(self):
        self.ensure_one()
        if self.env.context.get('skip_product_stock_update'):
            return
        product = self.product_id.sudo()
        if self.move_type == 'incoming':
            product.write({'stock': product.stock + self.quantity})
        elif self.move_type == 'outgoing':
            if product.stock < self.quantity:
                raise UserError(_(
                    "Insufficient stock for product %s.") % product.product_name)
            product.write({'stock': product.stock - self.quantity})
        elif self.move_type == 'adjustment':
            signed_qty = self.quantity
            if self.source_location_id and self.source_location_id.usage == 'internal':
                signed_qty = -self.quantity
            product.write({'stock': product.stock + signed_qty})

class Transfer(models.Model):
    _name = 'inventory.transfer'
    _inherit = ['inventory.access.mixin']
    _description = 'Inventory Transfers'
    _rec_name = 'transfer_number'
    _order = 'transfer_number desc, id desc'
    _menu_code = 'inventory_transfers'

    transfer_number = fields.Char(
        string="Transfer Number", readonly=True, copy=False)
    scheduled_date = fields.Date(
        string="Scheduled Date", default=fields.Date.today, required=True)
    source_location_id = fields.Many2one(
        'inventory.location', string="Source Location", ondelete='restrict')
    destination_location_id = fields.Many2one(
        'inventory.location', string="Destination Location", ondelete='restrict')
    operation_type = fields.Selection([
        ('incoming', 'Receipt'),
        ('outgoing', 'Delivery'),
        ('internal', 'Internal Transfer'),
    ], string="Operation Type", default='internal', required=True)
    source_document = fields.Char(string="Source Document", readonly=True)
    sales_order_id = fields.Many2one(
        'sales.sales_order', string="Sales Order", ondelete='set null')
    purchase_order_id = fields.Many2one(
        'purchases.purchase_order', string="Purchase Order", ondelete='set null')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    line_ids = fields.One2many(
        'inventory.transfer.line', 'transfer_id', string="Transfer Lines")
    note = fields.Text(string="Notes")
    is_edit = fields.Boolean(default=False)
    can_validate = fields.Boolean(
        compute='_compute_can_validate', store=False,
        help="True if at least one line has quantity > 0 and state is draft.")

    @api.depends('state', 'line_ids.quantity')
    def _compute_can_validate(self):
        for record in self:
            record.can_validate = (
                record.state == 'draft'
                and any(line.quantity > 0 for line in record.line_ids)
            )

    @api.model
    def _get_transfer_menu_code(self):
        """Resolve the correct menu code for access checks based on operation_type.
        Receipt and Delivery are filtered views of the same model but have
        separate menu entries in general.menu."""
        operation_type = self.env.context.get('default_operation_type')
        if operation_type == 'incoming':
            return 'inventory_receipts'
        elif operation_type == 'outgoing':
            return 'inventory_deliveries'
        return 'inventory_transfers'

    @api.model
    def _get_custom_access(self):
        """Override to use operation-specific menu code for Receipt/Delivery."""
        if self.env.user.has_group('base.group_system'):
            return True
        menu_code = self._get_transfer_menu_code()
        if not menu_code:
            return False
        return self.env['general.auth'].sudo().search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', menu_code),
        ], limit=1)

    def action_back(self):
        """Return to the appropriate filtered list based on operation_type."""
        self.ensure_one()
        if self.operation_type == 'incoming':
            try:
                return self.env.ref('inventory.inventory_receipt_action').sudo().read()[0]
            except Exception:
                pass
        elif self.operation_type == 'outgoing':
            try:
                return self.env.ref('inventory.inventory_delivery_action').sudo().read()[0]
            except Exception:
                pass
        return super().action_back()

    def _open_form(self):
        """Preserve operation_type context so menu-code resolution works
        after form reload (edit/save/cancel)."""
        self.ensure_one()
        res = super()._open_form()
        if self.operation_type:
            res.setdefault('context', {})
            res['context']['default_operation_type'] = self.operation_type
        return res

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_create', _("You do not have access rights to create transfers."))
        for vals in vals_list:
            if not vals.get('transfer_number'):
                sequence_code = 'inventory.transfer'
                if vals.get('operation_type') == 'incoming':
                    sequence_code = 'inventory.transfer.in'
                elif vals.get('operation_type') == 'outgoing':
                    sequence_code = 'inventory.transfer.out'
                vals['transfer_number'] = self.env['ir.sequence'].next_by_code(
                    sequence_code) or '/'
            if not vals.get('source_document'):
                if vals.get('purchase_order_id'):
                    po = self.env['purchases.purchase_order'].browse(
                        vals['purchase_order_id'])
                    vals['source_document'] = po.po_code
                elif vals.get('sales_order_id'):
                    so = self.env['sales.sales_order'].browse(
                        vals['sales_order_id'])
                    vals['source_document'] = so.sales_code
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_update', _("You do not have access rights to update transfers."))
        return super().write(vals)

    def unlink(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to delete transfers."))
        if any(transfer.state == 'done' for transfer in self):
            raise UserError(_("Done transfers cannot be deleted."))
        return super().unlink()

    def action_validate(self):
        self._check_custom_access(
            'can_confirm', _("You do not have access rights to validate transfers."))
        for transfer in self:
            if transfer.state != 'draft':
                raise UserError(_("Only draft transfers can be validated."))
            if not transfer.line_ids:
                raise UserError(_("Please add at least one product line."))
            moves = self.env['inventory.stock_move']
            received_by_po_line = {}
            delivered_by_so_line = {}
            for line in transfer.line_ids:
                if line.quantity <= 0:
                    raise UserError(_("Transfer quantity must be greater than zero."))
                if transfer.operation_type == 'incoming' and line.purchase_order_line_id:
                    po_line = line.purchase_order_line_id
                    received_by_po_line[po_line.id] = received_by_po_line.get(
                        po_line.id, 0.0) + line.quantity
                if transfer.operation_type == 'outgoing' and line.sales_order_line_id:
                    so_line = line.sales_order_line_id
                    delivered_by_so_line[so_line.id] = delivered_by_so_line.get(
                        so_line.id, 0.0) + line.quantity
            for po_line_id, quantity in received_by_po_line.items():
                po_line = self.env['purchases.purchase_order_line'].browse(
                    po_line_id)
                if quantity > po_line.qty_to_receive:
                    raise UserError(_(
                        "Received quantity cannot exceed the remaining quantity to receive."))
            for so_line_id, quantity in delivered_by_so_line.items():
                so_line = self.env['sales.sales_order_line'].browse(so_line_id)
                if quantity > so_line.qty_to_deliver:
                    raise UserError(_(
                        "Delivered quantity cannot exceed the remaining quantity to deliver."))
            for line in transfer.line_ids:
                move = moves.with_context(skip_inventory_access=True).create({
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'source_location_id': transfer.source_location_id.id,
                    'destination_location_id': transfer.destination_location_id.id,
                    'move_type': transfer.operation_type,
                    'origin': transfer.transfer_number,
                    'origin_model': 'inventory.transfer',
                    'origin_id': transfer.id,
                    'origin_line_id': line.id,
                })
                move.with_context(skip_inventory_access=True).action_done()
                if transfer.operation_type == 'incoming' and line.purchase_order_line_id:
                    line.purchase_order_line_id.write({
                        'qty_received': line.purchase_order_line_id.qty_received + line.quantity
                    })
                if transfer.operation_type == 'outgoing' and line.sales_order_line_id:
                    line.sales_order_line_id.write({
                        'qty_delivered': line.sales_order_line_id.qty_delivered + line.quantity
                    })
            if transfer.operation_type == 'incoming' and transfer.purchase_order_id:
                transfer._create_purchase_receipt_from_transfer()
            if transfer.operation_type == 'outgoing' and transfer.sales_order_id:
                transfer._create_sales_delivery_from_transfer()
            transfer.with_context(skip_inventory_access=True).write({
                'state': 'done',
                'is_edit': False,
            })

            # --- Auto-create next transfer for remaining quantities ---
            transfer._create_remaining_transfer()

        return True

    def _create_remaining_transfer(self):
        """After validation, if there are still products with remaining
        qty_to_receive (incoming) or qty_to_deliver (outgoing), automatically
        create a new draft transfer for those remaining quantities."""
        self.ensure_one()

        if self.operation_type == 'incoming' and self.purchase_order_id:
            po = self.purchase_order_id
            remaining_lines = po.order_line_ids.filtered(
                lambda l: l.product_id and l.qty_to_receive > 0)
            if not remaining_lines:
                return False

            # Skip if a draft transfer already exists for this PO
            existing_draft = po.inventory_receipt_transfer_ids.filtered(
                lambda t: t.state == 'draft' and t.id != self.id)
            if existing_draft:
                return False

            supplier_location = self.env.ref(
                'inventory.inventory_location_supplier', raise_if_not_found=False)
            stock_location = self.env.ref(
                'inventory.inventory_location_stock', raise_if_not_found=False)

            self.env['inventory.transfer'].with_context(
                skip_inventory_access=True
            ).create({
                'scheduled_date': fields.Date.today(),
                'operation_type': 'incoming',
                'source_location_id': supplier_location.id if supplier_location else False,
                'destination_location_id': stock_location.id if stock_location else False,
                'purchase_order_id': po.id,
                'source_document': po.po_code,
                'state': 'draft',
                'note': _(
                    'Created automatically to fulfill remaining receipt '
                    'from %s.'
                ) % self.transfer_number,
                'line_ids': [(0, 0, {
                    'purchase_order_line_id': line.id,
                    'product_id': line.product_id.id,
                    'quantity': 0.0,
                }) for line in remaining_lines],
            })
            return True

        if self.operation_type == 'outgoing' and self.sales_order_id:
            so = self.sales_order_id
            remaining_lines = so.order_line_ids.filtered(
                lambda l: l.product_id and l.qty_to_deliver > 0)
            if not remaining_lines:
                return False

            # Skip if a draft transfer already exists for this SO
            existing_draft = so.inventory_transfer_ids.filtered(
                lambda t: t.state == 'draft' and t.id != self.id)
            if existing_draft:
                return False

            stock_location = self.env.ref(
                'inventory.inventory_location_stock', raise_if_not_found=False)
            customer_location = self.env.ref(
                'inventory.inventory_location_customer', raise_if_not_found=False)

            self.env['inventory.transfer'].with_context(
                skip_inventory_access=True
            ).create({
                'scheduled_date': (
                    so.commitment_date or fields.Date.today()
                ),
                'operation_type': 'outgoing',
                'source_location_id': stock_location.id if stock_location else False,
                'destination_location_id': customer_location.id if customer_location else False,
                'sales_order_id': so.id,
                'source_document': so.sales_code,
                'state': 'draft',
                'note': _(
                    'Created automatically to fulfill remaining delivery '
                    'from %s.'
                ) % self.transfer_number,
                'line_ids': [(0, 0, {
                    'sales_order_line_id': line.id,
                    'product_id': line.product_id.id,
                    'quantity': 0.0,
                }) for line in remaining_lines],
            })
            return True

        return False

    def _create_purchase_receipt_from_transfer(self):
        self.ensure_one()
        receipt_lines = []
        received_lines = self.line_ids.filtered(
            lambda l: l.purchase_order_line_id and l.quantity > 0)
        for line in received_lines:
            po_line = line.purchase_order_line_id
            receipt_lines.append((0, 0, {
                'purchase_order_line_id': po_line.id,
                'product_id': line.product_id.id,
                'description': po_line.description or line.product_id.product_name,
                'ordered_qty': po_line.quantity,
                'quantity': line.quantity,
            }))
        if not receipt_lines:
            return False

        existing_receipt = self.env['purchases.receipt'].sudo().search([
            ('purchase_order_id', '=', self.purchase_order_id.id),
            ('note', 'ilike', self.transfer_number),
            ('state', '!=', 'cancel'),
        ], limit=1)
        if existing_receipt:
            return existing_receipt

        return self.env['purchases.receipt'].with_context(
            allow_internal_receipt_create=True
        ).sudo().create({
            'purchase_order_id': self.purchase_order_id.id,
            'vendor_id': self.purchase_order_id.vendor_id.id,
            'buyer_id': (
                self.purchase_order_id.buyer_id.id
                if self.purchase_order_id.buyer_id else False
            ),
            'receipt_date': self.scheduled_date or fields.Date.today(),
            'state': 'received',
            'received_date': fields.Datetime.now(),
            'note': _(
                'Created automatically from Inventory Transfer %s.'
            ) % self.transfer_number,
            'line_ids': receipt_lines,
        })

    def _create_sales_delivery_from_transfer(self):
        self.ensure_one()
        delivery_lines = []
        delivered_lines = self.line_ids.filtered(
            lambda l: l.sales_order_line_id and l.quantity > 0)
        for line in delivered_lines:
            so_line = line.sales_order_line_id
            delivery_lines.append((0, 0, {
                'sales_order_line_id': so_line.id,
                'product_id': line.product_id.id,
                'description': so_line.product_id.product_name if so_line.product_id else '',
                'ordered_qty': so_line.quantity,
                'quantity': line.quantity,
            }))
        if not delivery_lines:
            return False

        existing_delivery = self.env['sales.delivery'].sudo().search([
            ('sales_order_id', '=', self.sales_order_id.id),
            ('note', 'ilike', self.transfer_number),
            ('state', '!=', 'cancel'),
        ], limit=1)
        if existing_delivery:
            return existing_delivery

        return self.env['sales.delivery'].sudo().with_context(
            allow_internal_delivery_create=True
        ).create({
            'sales_order_id': self.sales_order_id.id,
            'customer_id': (
                self.sales_order_id.customer_id.id
                if self.sales_order_id.customer_id else False
            ),
            'delivery_date': self.scheduled_date or fields.Date.today(),
            'state': 'done',
            'done_date': fields.Datetime.now(),
            'note': _(
                'Created automatically from Inventory Transfer %s.'
            ) % self.transfer_number,
            'line_ids': delivery_lines,
        })

    def action_cancel(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to cancel transfers."))
        for transfer in self:
            if transfer.state == 'done':
                raise UserError(_("Done transfers cannot be cancelled."))
            transfer.with_context(skip_inventory_access=True).write({
                'state': 'cancel',
                'is_edit': False,
            })
        return True


class TransferLine(models.Model):
    _name = 'inventory.transfer.line'
    _description = 'Inventory Transfer Lines'

    transfer_id = fields.Many2one(
        'inventory.transfer', string="Transfer", ondelete='cascade', required=True)
    purchase_order_line_id = fields.Many2one(
        'purchases.purchase_order_line', string="PO Line",
        ondelete='set null', index=True)
    sales_order_line_id = fields.Many2one(
        'sales.sales_order_line', string="SO Line",
        ondelete='set null', index=True)
    product_id = fields.Many2one(
        'sales.products', string="Product", ondelete='restrict', required=True)
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM", readonly=True)
    quantity = fields.Float(string="Quantity", required=True, default=0.0)
    available_stock = fields.Integer(
        related='product_id.stock', string="On Hand", readonly=True)

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            if record.quantity < 0:
                raise ValidationError(_("Quantity cannot be negative."))


class Adjustment(models.Model):
    _name = 'inventory.adjustment'
    _inherit = ['inventory.access.mixin']
    _description = 'Inventory Adjustments'
    _rec_name = 'adjustment_number'
    _order = 'adjustment_number desc, id desc'
    _menu_code = 'inventory_adjustments'

    adjustment_number = fields.Char(
        string="Adjustment Number", readonly=True, copy=False)
    adjustment_date = fields.Date(
        string="Adjustment Date", default=fields.Date.today, required=True)
    location_id = fields.Many2one(
        'inventory.location', string="Location", ondelete='restrict')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    line_ids = fields.One2many(
        'inventory.adjustment.line', 'adjustment_id', string="Adjustment Lines")
    note = fields.Text(string="Notes")
    is_edit = fields.Boolean(default=False)
    can_validate = fields.Boolean(
        compute='_compute_can_validate', store=False,
        help="True if at least one line has counted_qty > 0 and state is draft.")

    all_products_added = fields.Boolean(
        compute='_compute_all_products_added', store=False)

    @api.depends('state', 'line_ids.counted_qty')
    def _compute_can_validate(self):
        for record in self:
            record.can_validate = (
                record.state == 'draft'
                and any(line.counted_qty > 0 for line in record.line_ids)
            )

    @api.depends('line_ids.product_id')
    def _compute_all_products_added(self):
        for record in self:
            if not record.id:
                record.all_products_added = False
                continue
            total = self.env['sales.products'].search_count([])
            added = len(record.line_ids)
            record.all_products_added = total > 0 and added >= total

    @api.model_create_multi
    def create(self, vals_list):
        self._check_custom_access(
            'can_create', _("You do not have access rights to create inventory adjustments."))
        for vals in vals_list:
            if not vals.get('adjustment_number'):
                vals['adjustment_number'] = self.env['ir.sequence'].next_by_code(
                    'inventory.adjustment') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('skip_inventory_access'):
            self._check_custom_access(
                'can_update', _("You do not have access rights to update inventory adjustments."))
        return super().write(vals)

    def unlink(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to delete inventory adjustments."))
        if any(adjustment.state == 'done' for adjustment in self):
            raise UserError(_("Done adjustments cannot be deleted."))
        return super().unlink()

    def action_validate(self):
        self._check_custom_access(
            'can_confirm', _("You do not have access rights to validate inventory adjustments."))
        inventory_location = self.env.ref(
            'inventory.inventory_location_inventory', raise_if_not_found=False)
        for adjustment in self:
            if adjustment.state != 'draft':
                raise UserError(_("Only draft adjustments can be validated."))
            if not adjustment.line_ids:
                raise UserError(_("Please add at least one product line."))
            for line in adjustment.line_ids:
                difference = line.counted_qty - line.current_qty
                if difference == 0:
                    continue
                source_location = inventory_location
                destination_location = adjustment.location_id
                quantity = abs(difference)
                if difference < 0:
                    source_location = adjustment.location_id
                    destination_location = inventory_location
                move = self.env['inventory.stock_move'].with_context(skip_inventory_access=True).create({
                    'product_id': line.product_id.id,
                    'quantity': quantity,
                    'source_location_id': source_location.id if source_location else False,
                    'destination_location_id': destination_location.id if destination_location else False,
                    'move_type': 'adjustment',
                    'origin': adjustment.adjustment_number,
                    'origin_model': 'inventory.adjustment',
                    'origin_id': adjustment.id,
                    'origin_line_id': line.id,
                })
                move.with_context(skip_inventory_access=True).action_done()
            adjustment.with_context(skip_inventory_access=True).write({
                'state': 'done',
                'is_edit': False,
            })
        return True

    def action_add_product(self):
        self.ensure_one()
        return {
            'name': _('Add Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'inventory.adjustment.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_adjustment_id': self.id,
                'default_is_edit': True,
            },
        }

    def action_cancel(self):
        self._check_custom_access(
            'can_delete', _("You do not have access rights to cancel inventory adjustments."))
        for adjustment in self:
            if adjustment.state == 'done':
                raise UserError(_("Done adjustments cannot be cancelled."))
            adjustment.with_context(skip_inventory_access=True).write({
                'state': 'cancel',
                'is_edit': False,
            })
        return True


class AdjustmentLine(models.Model):
    _name = 'inventory.adjustment.line'
    _description = 'Inventory Adjustment Lines'

    adjustment_id = fields.Many2one(
        'inventory.adjustment', string="Adjustment", ondelete='cascade', required=True)
    product_id = fields.Many2one(
        'sales.products', string="Product", ondelete='restrict', required=True)
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM", readonly=True)
    current_qty = fields.Integer(
        string="Current Quantity", readonly=True, copy=False)
    counted_qty = fields.Float(string="Counted Quantity", required=True)
    difference_qty = fields.Float(
        string="Difference", compute='_compute_difference_qty')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.current_qty = self.product_id.stock

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and 'current_qty' not in vals:
                product = self.env['sales.products'].browse(
                    vals['product_id'])
                vals['current_qty'] = product.stock
        return super().create(vals_list)

    @api.depends('counted_qty', 'current_qty')
    def _compute_difference_qty(self):
        for record in self:
            record.difference_qty = record.counted_qty - record.current_qty

    def action_open_wizard(self):
        self.ensure_one()
        return {
            'name': _('Product Detail'),
            'type': 'ir.actions.act_window',
            'res_model': 'inventory.adjustment.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_adjustment_id': self.adjustment_id.id,
            },
        }

    def action_delete_line(self):
        self.ensure_one()
        adjustment = self.adjustment_id
        self.unlink()
        # Auto-save adjustment after delete
        adjustment.with_context(
            skip_inventory_access=True
        ).write({'is_edit': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'inventory.adjustment',
            'view_mode': 'form',
            'res_id': adjustment.id,
            'target': 'current',
        }


class AdjustmentLineWizard(models.TransientModel):
    _name = 'inventory.adjustment.line.wizard'
    _description = 'Add/Edit Adjustment Line'

    adjustment_id = fields.Many2one(
        'inventory.adjustment', string="Adjustment",
        required=True, ondelete='cascade')
    line_id = fields.Many2one(
        'inventory.adjustment.line', string="Line",
        ondelete='cascade', readonly=True)
    product_id = fields.Many2one(
        'sales.products', string="Product", required=True,
        domain=[('sales_ok', '=', True)])
    current_qty = fields.Integer(
        string="Current Quantity", compute='_compute_current_qty')
    counted_qty = fields.Float(string="Counted Quantity")
    is_edit = fields.Boolean(default=False)

    @api.depends('product_id')
    def _compute_current_qty(self):
        for record in self:
            if record.product_id:
                record.current_qty = record.product_id.stock
            else:
                record.current_qty = 0

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        default_line_id = self.env.context.get('default_line_id')
        if default_line_id:
            line = self.env['inventory.adjustment.line'].browse(
                default_line_id)
            if line.exists():
                res.update({
                    'line_id': line.id,
                    'adjustment_id': line.adjustment_id.id,
                    'product_id': line.product_id.id,
                    'current_qty': line.current_qty,
                    'counted_qty': line.counted_qty,
                })
        return res

    def action_edit(self):
        self.ensure_one()
        self.is_edit = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_save(self):
        self.ensure_one()
        if not self.line_id:
            duplicate = self.adjustment_id.line_ids.filtered(
                lambda l: l.product_id == self.product_id)
            if duplicate:
                raise UserError(_(
                    "Product '%s' is already in the list."
                ) % self.product_id.display_name)
            self.env['inventory.adjustment.line'].with_context(
                skip_inventory_access=True
            ).create({
                'adjustment_id': self.adjustment_id.id,
                'product_id': self.product_id.id,
                'current_qty': self.current_qty,
                'counted_qty': self.counted_qty,
            })
        else:
            self.line_id.with_context(
                skip_inventory_access=True
            ).write({'counted_qty': self.counted_qty})
        # Auto-save adjustment to prevent data loss during long stock-taking
        self.adjustment_id.with_context(
            skip_inventory_access=True
        ).write({'is_edit': False})
        return {'type': 'ir.actions.act_window_close'}

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}


class ProductInventory(models.Model):
    _inherit = 'sales.products'

    inventory_move_ids = fields.One2many(
        'inventory.stock_move', 'product_id', string="Inventory Moves")

    def action_open_inventory_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Inventory Moves'),
            'res_model': 'inventory.stock_move',
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', self.id)],
            'context': {'create': False},
        }


class PurchaseOrderInventory(models.Model):
    _inherit = 'purchases.purchase_order'

    inventory_receipt_transfer_ids = fields.One2many(
        'inventory.transfer', 'purchase_order_id', string="Receipt Transfers")

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_auto_inventory_receipt_transfer'):
            self._ensure_inventory_receipt_transfer()
        return res

    def _ensure_inventory_receipt_transfer(self):
        supplier_location = self.env.ref(
            'inventory.inventory_location_supplier', raise_if_not_found=False)
        stock_location = self.env.ref(
            'inventory.inventory_location_stock', raise_if_not_found=False)
        if not supplier_location or not stock_location:
            return

        for order in self:
            if order.receipt_status != 'to_receive':
                continue
            remaining_lines = order.order_line_ids.filtered(
                lambda line: line.product_id and line.qty_to_receive > 0)
            if not remaining_lines:
                continue
            existing_transfer = order.inventory_receipt_transfer_ids.filtered(
                lambda transfer: transfer.state != 'cancel')[:1]
            if existing_transfer:
                continue

            order.env['inventory.transfer'].with_context(
                skip_inventory_access=True, default_state=False
            ).create({
                'scheduled_date': fields.Date.today(),
                'operation_type': 'incoming',
                'source_location_id': supplier_location.id,
                'destination_location_id': stock_location.id,
                'purchase_order_id': order.id,
                'source_document': order.po_code,
                'state': 'draft',
                'note': _('Created from Purchase Order %s.') % order.po_code,
                'line_ids': [(0, 0, {
                    'purchase_order_line_id': line.id,
                    'product_id': line.product_id.id,
                    'quantity': 0.0,
                }) for line in remaining_lines],
            })


class SalesOrderInventory(models.Model):
    _inherit = 'sales.sales_order'

    inventory_transfer_ids = fields.One2many(
        'inventory.transfer', 'sales_order_id', string="Delivery Transfers")
    inventory_delivery_count = fields.Integer(
        compute='_compute_inventory_delivery_count')
    delivery_status = fields.Selection([
        ('no', 'No Delivery'),
        ('to_deliver', 'To Deliver'),
        ('partial', 'Partially Delivered'),
        ('delivered', 'Fully Delivered'),
    ], string="Delivery Status", compute='_compute_delivery_status', store=True)

    @api.depends('inventory_transfer_ids')
    def _compute_inventory_delivery_count(self):
        for order in self:
            order.inventory_delivery_count = len(order.inventory_transfer_ids)

    @api.depends('state', 'order_line_ids.quantity', 'order_line_ids.qty_delivered')
    def _compute_delivery_status(self):
        for order in self:
            if order.state != 'sale' or not order.order_line_ids:
                order.delivery_status = 'no'
                continue
            total_qty = sum(order.order_line_ids.mapped('quantity'))
            delivered_qty = sum(order.order_line_ids.mapped('qty_delivered'))
            if not total_qty:
                order.delivery_status = 'no'
            elif delivered_qty <= 0:
                order.delivery_status = 'to_deliver'
            elif delivered_qty >= total_qty:
                order.delivery_status = 'delivered'
            else:
                order.delivery_status = 'partial'

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_auto_inventory_delivery_transfer'):
            self._ensure_inventory_delivery_transfer()
        return res

    def _ensure_inventory_delivery_transfer(self):
        stock_location = self.env.ref(
            'inventory.inventory_location_stock', raise_if_not_found=False)
        customer_location = self.env.ref(
            'inventory.inventory_location_customer', raise_if_not_found=False)
        if not stock_location or not customer_location:
            return

        for order in self:
            if order.state != 'sale':
                continue
            remaining_lines = order.order_line_ids.filtered(
                lambda line: line.product_id and line.qty_to_deliver > 0)
            if not remaining_lines:
                continue
            existing_transfer = order.inventory_transfer_ids.filtered(
                lambda transfer: transfer.state != 'cancel')[:1]
            if existing_transfer:
                continue

            order.env['inventory.transfer'].with_context(
                skip_inventory_access=True, default_state=False
            ).create({
                'scheduled_date': order.commitment_date or fields.Date.today(),
                'operation_type': 'outgoing',
                'source_location_id': stock_location.id,
                'destination_location_id': customer_location.id,
                'sales_order_id': order.id,
                'source_document': order.sales_code,
                'state': 'draft',
                'note': _('Created from Sales Order %s.') % order.sales_code,
                'line_ids': [(0, 0, {
                    'sales_order_line_id': line.id,
                    'product_id': line.product_id.id,
                    'quantity': 0.0,
                }) for line in remaining_lines],
            })

    delivery_ids = fields.One2many(
        'sales.delivery', 'sales_order_id', string="Delivery Orders")
    delivery_count = fields.Integer(
        string='Delivery Count', compute='_compute_delivery_count')

    def _compute_delivery_count(self):
        for order in self:
            order.delivery_count = len(order.delivery_ids.filtered(
                lambda d: d.state != 'cancel'))

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Orders'),
            'res_model': 'sales.delivery',
            'view_mode': 'tree,form',
            'domain': [('sales_order_id', '=', self.id)],
            'context': {'default_sales_order_id': self.id},
        }

    def action_create_inventory_delivery(self):
        self.ensure_one()
        if self.state != 'sale':
            raise UserError(_("Delivery can only be created from a sales order."))
        draft_transfer = self.inventory_transfer_ids.filtered(
            lambda transfer: transfer.state == 'draft')[:1]
        if draft_transfer:
            return draft_transfer._open_form()
        order_lines = self.order_line_ids.filtered(
            lambda line: line.product_id and line.qty_to_deliver > 0)
        if not order_lines:
            raise UserError(_("All products on this sales order have already been delivered."))
        stock_location = self.env.ref(
            'inventory.inventory_location_stock', raise_if_not_found=False)
        customer_location = self.env.ref(
            'inventory.inventory_location_customer', raise_if_not_found=False)
        transfer = self.env['inventory.transfer'].with_context(
            skip_inventory_access=True, default_state=False
        ).create({
            'scheduled_date': self.commitment_date or fields.Date.today(),
            'source_location_id': stock_location.id if stock_location else False,
            'destination_location_id': customer_location.id if customer_location else False,
            'operation_type': 'outgoing',
            'sales_order_id': self.id,
            'source_document': self.sales_code,
            'state': 'draft',
            'note': _('Created from Sales Order %s.') % self.sales_code,
            'line_ids': [(0, 0, {
                'sales_order_line_id': line.id,
                'product_id': line.product_id.id,
                'quantity': line.qty_to_deliver,
            }) for line in order_lines],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Transfer'),
            'res_model': 'inventory.transfer',
            'view_mode': 'form',
            'res_id': transfer.id,
            'target': 'current',
        }

    def action_view_inventory_deliveries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Transfers'),
            'res_model': 'inventory.transfer',
            'view_mode': 'tree,form',
            'domain': [('sales_order_id', '=', self.id)],
            'context': {'default_sales_order_id': self.id},
        }


class SalesOrderLineInventory(models.Model):
    _inherit = 'sales.sales_order_line'

    qty_delivered = fields.Float(string="Delivered", default=0.0, copy=False)
    qty_to_deliver = fields.Float(
        string="To Deliver", compute='_compute_qty_to_deliver', store=True)

    @api.depends('quantity', 'qty_delivered')
    def _compute_qty_to_deliver(self):
        for record in self:
            record.qty_to_deliver = max(
                (record.quantity or 0.0) - (record.qty_delivered or 0.0), 0.0)


class PurchaseReceiptInventory(models.Model):
    _inherit = 'purchases.receipt'

    def action_receive(self):
        previous_draft = {
            receipt.id for receipt in self if receipt.state == 'draft'
        }
        res = super().action_receive()
        supplier_location = self.env.ref(
            'inventory.inventory_location_supplier', raise_if_not_found=False)
        stock_location = self.env.ref(
            'inventory.inventory_location_stock', raise_if_not_found=False)
        for receipt in self.filtered(lambda r: r.id in previous_draft and r.state == 'received'):
            for line in receipt.line_ids:
                existing_move = self.env['inventory.stock_move'].sudo().search([
                    ('origin_model', '=', 'purchases.receipt'),
                    ('origin_id', '=', receipt.id),
                    ('origin_line_id', '=', line.id),
                ], limit=1)
                if existing_move:
                    continue
                self.env['inventory.stock_move'].sudo().create({
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'source_location_id': supplier_location.id if supplier_location else False,
                    'destination_location_id': stock_location.id if stock_location else False,
                    'move_type': 'incoming',
                    'state': 'done',
                    'date': receipt.received_date or fields.Datetime.now(),
                    'origin': receipt.receipt_number,
                    'origin_model': 'purchases.receipt',
                    'origin_id': receipt.id,
                    'origin_line_id': line.id,
                    'note': _('Created automatically from Purchase Receipt.'),
                })
        return res
