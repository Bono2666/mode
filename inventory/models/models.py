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
            elif access:
                record.user_can_create = access.can_create
                record.user_can_update = access.can_update
                record.user_can_delete = access.can_delete
            else:
                record.user_can_create = False
                record.user_can_update = False
                record.user_can_delete = False

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

    def _back_action(self):
        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'tree,form',
            'target': 'main',
            'context': self.env.context,
        }


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

    def action_open_origin(self):
        self.ensure_one()
        if not self.origin_model or not self.origin_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.origin or self.origin_model,
            'res_model': self.origin_model,
            'view_mode': 'form',
            'res_id': self.origin_id,
            'target': 'current',
        }


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
    sales_order_id = fields.Many2one(
        'sales.sales_order', string="Sales Order", ondelete='set null')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    line_ids = fields.One2many(
        'inventory.transfer.line', 'transfer_id', string="Transfer Lines")
    note = fields.Text(string="Notes")
    is_edit = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_custom_access(
            'can_create', _("You do not have access rights to create transfers."))
        for vals in vals_list:
            if not vals.get('transfer_number'):
                vals['transfer_number'] = self.env['ir.sequence'].next_by_code(
                    'inventory.transfer') or '/'
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
            for line in transfer.line_ids:
                if line.quantity <= 0:
                    raise UserError(_("Transfer quantity must be greater than zero."))
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
            transfer.with_context(skip_inventory_access=True).write({
                'state': 'done',
                'is_edit': False,
            })
        return True

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
    product_id = fields.Many2one(
        'sales.products', string="Product", ondelete='restrict', required=True)
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM", readonly=True)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    available_stock = fields.Integer(
        related='product_id.stock', string="On Hand", readonly=True)

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))


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
        related='product_id.stock', string="Current Quantity", readonly=True)
    counted_qty = fields.Float(string="Counted Quantity", required=True)
    difference_qty = fields.Float(
        string="Difference", compute='_compute_difference_qty')

    @api.depends('counted_qty', 'current_qty')
    def _compute_difference_qty(self):
        for record in self:
            record.difference_qty = record.counted_qty - record.current_qty


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


class SalesOrderInventory(models.Model):
    _inherit = 'sales.sales_order'

    inventory_transfer_ids = fields.One2many(
        'inventory.transfer', 'sales_order_id', string="Delivery Transfers")
    inventory_delivery_count = fields.Integer(
        compute='_compute_inventory_delivery_count')

    @api.depends('inventory_transfer_ids')
    def _compute_inventory_delivery_count(self):
        for order in self:
            order.inventory_delivery_count = len(order.inventory_transfer_ids)

    def action_create_inventory_delivery(self):
        self.ensure_one()
        if self.state != 'sale':
            raise UserError(_("Delivery can only be created from a sales order."))
        order_lines = self.order_line_ids.filtered(
            lambda line: line.product_id and line.quantity > 0)
        if not order_lines:
            raise UserError(_("Please add at least one product line."))
        stock_location = self.env.ref(
            'inventory.inventory_location_stock', raise_if_not_found=False)
        customer_location = self.env.ref(
            'inventory.inventory_location_customer', raise_if_not_found=False)
        transfer = self.env['inventory.transfer'].create({
            'scheduled_date': self.commitment_date or fields.Date.today(),
            'source_location_id': stock_location.id if stock_location else False,
            'destination_location_id': customer_location.id if customer_location else False,
            'operation_type': 'outgoing',
            'sales_order_id': self.id,
            'note': _('Created from Sales Order %s.') % self.sales_code,
            'line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'quantity': line.quantity,
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
