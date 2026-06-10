from datetime import timedelta
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


# ─────────────────────────────────────────────
#  SIMPLE EDIT MIXIN
# ─────────────────────────────────────────────

class PurchaseEditMixin(models.AbstractModel):
    _name = 'purchases.edit.mixin'
    _description = 'Simple Edit/Save/Back Mixin for Purchases'

    is_edit = fields.Boolean(default=False)

    def action_edit(self):
        self.ensure_one()
        self.write({'is_edit': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_save(self):
        self.ensure_one()
        self.write({'is_edit': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_back(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
        }

    def action_delete(self):
        self.ensure_one()
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
        }


# ─────────────────────────────────────────────
#  VENDOR
# ─────────────────────────────────────────────

class vendor(models.Model):
    _name = 'purchases.vendor'
    _inherit = ['purchases.edit.mixin']
    _description = 'Vendors'
    _rec_name = 'vendor_name'

    vendor_id = fields.Char(string="Vendor ID", readonly=True)
    vendor_name = fields.Char(string="Vendor Name", required=True)
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
    npwp = fields.Char(string="NPWP")
    contact_name = fields.Char(string="Contact Name")
    telephone = fields.Char(string="Telephone")
    email = fields.Char(string="Email")
    website = fields.Char(string="Website")
    payment_terms = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms',
        ondelete='set null', index=True)
    is_edit = fields.Boolean(default=False)
    partner_id = fields.Many2one(
        'res.partner', string="Related Partner", ondelete='cascade')
    image_1920 = fields.Image(
        string="Image", compute='_compute_image_1920', inverse='_inverse_image_1920')

    def _compute_image_1920(self):
        for record in self:
            record.image_1920 = record.partner_id.sudo(
            ).image_1920 if record.partner_id else False

    def _inverse_image_1920(self):
        for record in self:
            if record.partner_id:
                record.partner_id.sudo().write(
                    {'image_1920': record.image_1920})

    @api.model_create_multi
    def create(self, vals_list):
        partner_model = self.env['res.partner'].sudo()
        for vals in vals_list:
            if not vals.get('vendor_id'):
                vals['vendor_id'] = self.env['ir.sequence'].next_by_code(
                    'purchases.vendor') or '/'

            partner_vals = {
                'name': vals.get('vendor_name'),
                'email': vals.get('email'),
                'phone': vals.get('telephone'),
                'website': vals.get('website'),
                'street': vals.get('address'),
                'is_company': True,
            }
            if vals.get('image_1920'):
                partner_vals['image_1920'] = vals.get('image_1920')
            if 'supplier_rank' in partner_model._fields:
                partner_vals['supplier_rank'] = 1

            partner = partner_model.create(partner_vals)
            vals['partner_id'] = partner.id
        return super(vendor, self).create(vals_list)

    def write(self, vals):
        res = super(vendor, self).write(vals)
        partner_vals = {}
        if 'vendor_name' in vals:
            partner_vals['name'] = vals['vendor_name']
        if 'email' in vals:
            partner_vals['email'] = vals['email']
        if 'telephone' in vals:
            partner_vals['phone'] = vals['telephone']
        if 'address' in vals:
            partner_vals['street'] = vals['address']
        if partner_vals:
            for rec in self:
                if rec.partner_id:
                    rec.partner_id.sudo().write(partner_vals)
        return res

    def unlink(self):
        partners = self.mapped('partner_id')
        res = super(vendor, self).unlink()
        if partners:
            partners.sudo().unlink()
        return res


class VendorDisplayName(models.Model):
    """Override display_name vendor agar menampilkan email di wizard."""
    _inherit = 'purchases.vendor'

    @api.depends('vendor_name', 'email')
    def _compute_display_name(self):
        show_email = self.env.context.get('show_email_in_wizard')
        for record in self:
            if show_email and record.email:
                record.display_name = f"{record.vendor_name} <{record.email}>"
            else:
                record.display_name = record.vendor_name or ''


class MailComposeMessagePurchase(models.TransientModel):
    """Extend mail.compose.message untuk mendukung vendor sebagai recipients."""
    _inherit = 'mail.compose.message'

    vendor_ids = fields.Many2many(
        'purchases.vendor',
        string='Vendors',
        context={'show_email_in_wizard': True},
        help="Select vendors to add as recipients"
    )

    @api.onchange('vendor_ids')
    def _onchange_vendor_ids(self):
        """Sync vendor yang dipilih ke field partner_ids standar Odoo."""
        if self.vendor_ids:
            partner_ids = self.vendor_ids.mapped('partner_id.id')
            existing = self.partner_ids.ids
            merged = list(set(existing + partner_ids))
            self.partner_ids = [(6, 0, merged)]

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


# ─────────────────────────────────────────────
#  PURCHASE ORDER
# ─────────────────────────────────────────────

class purchase_order(models.Model):
    _name = 'purchases.purchase_order'
    _inherit = ['purchases.edit.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Purchase Orders'
    _rec_name = 'po_code'
    _order = 'po_code desc'
    _menu_code = 'purchase_order'

    po_code = fields.Char(string="PO Number", readonly=True)
    entry_menu_code = fields.Char(string="Entry Menu Code", copy=False)
    vendor_id = fields.Many2one(
        comodel_name='purchases.vendor', string='Vendor',
        index=True, required=True)
    vendor_address = fields.Text(
        compute='_compute_vendor_address', string="Vendor Address")
    po_date = fields.Date(
        string="Order Date", default=fields.Date.today)
    delivery_date = fields.Date(string="Delivery Date")
    payment_terms = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms',
        ondelete='set null', index=True)
    buyer_id = fields.Many2one(
        comodel_name='general.custom_users', string='Buyer',
        ondelete='set null', index=True,
        default=lambda self: self.env['general.custom_users'].search(
            [('user_id', '=', self.env.uid)], limit=1))
    order_line_ids = fields.One2many(
        'purchases.purchase_order_line', 'purchase_order_id', string='Order Lines')
    total_amount_untaxed = fields.Float(
        string="Untaxed Total", compute='_compute_total_amount',
        store=True, digits=(16, 0))
    total_tax = fields.Float(
        string="Total Tax", compute='_compute_total_amount',
        store=True, digits=(16, 0))
    total_amount = fields.Float(
        string="Total", compute='_compute_total_amount',
        store=True, digits=(16, 0))
    approval_log_ids = fields.One2many(
        'purchases.purchase_approval_log', 'purchase_order_id', string="Approval Logs")
    need_approval = fields.Boolean(
        compute='_compute_need_approval', store=True)
    approval_status = fields.Selection([
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Approval Status", default='pending')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'RFQ'),
        ('purchase', 'Purchase Order'),
        ('wait_approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    bill_ids = fields.One2many(
        'purchases.bill', 'purchase_order_id', string='Bills')
    bill_count = fields.Integer(
        string='Bill Count', compute='_compute_bill_count')
    bill_status = fields.Selection([
        ('no', 'Nothing to Bill'),
        ('to_bill', 'Waiting Bills'),
        ('billed', 'Fully Billed'),
    ], string="Billing Status", compute='_compute_bill_status', store=True)
    receipt_ids = fields.One2many(
        'purchases.receipt', 'purchase_order_id', string='Receipts')
    receipt_count = fields.Integer(
        string='Receipt Count', compute='_compute_receipt_count')
    receipt_status = fields.Selection([
        ('no', 'Nothing to Receive'),
        ('to_receive', 'Waiting Receipt'),
        ('partial', 'Partially Received'),
        ('received', 'Fully Received'),
    ], string="Receipt Status", compute='_compute_receipt_status', store=True)
    current_approver = fields.Integer(
        string="Pending Approval From", compute='_compute_current_approver', store=True)
    current_approver_name = fields.Char(
        compute='_compute_current_approver', store=True)
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
    user_can_confirm_order = fields.Boolean(
        string="User Can Confirm Order", compute='_compute_confirm_order_permissions')
    user_can_cancel_order = fields.Boolean(
        string="User Can Cancel Order", compute='_compute_cancel_order_permissions')
    user_can_send = fields.Boolean(
        string="User Can Send", compute='_compute_send_permissions')
    user_can_receive = fields.Boolean(
        string="User Can Receive", compute='_compute_receive_permissions')
    user_can_update = fields.Boolean(
        string="User Can Update", compute='_compute_update_permissions')
    user_can_delete = fields.Boolean(
        string="User Can Delete", compute='_compute_delete_permissions')
    user_can_billing = fields.Boolean(
        string="User Can Billing", compute='_compute_billing_permissions')
    is_sent = fields.Boolean(
        string="Has Been Sent", default=False, copy=False,
        help="Becomes True permanently once the PO has been sent by email.")
    note = fields.Text(string="Terms and Conditions")

    @api.depends('vendor_id')
    def _compute_vendor_address(self):
        for record in self:
            parts = []
            v = record.vendor_id
            if v.address:
                parts.append(v.address)
            if v.district:
                parts.append(v.district.district_name)
            if v.city:
                parts.append(v.city.city_name)
            if v.state:
                parts.append(v.state.state_name)
            if v.postal_code:
                parts.append(v.postal_code)
            if v.country:
                parts.append(v.country.country_name)
            record.vendor_address = ', '.join(parts)

    @api.onchange('delivery_date')
    def _onchange_delivery_date(self):
        if self.delivery_date and self.delivery_date < fields.Date.today():
            self.delivery_date = False
            return {
                'warning': {
                    'title': _('Invalid Delivery Date'),
                    'message': _('Delivery Date cannot be earlier than today.'),
                }
            }

    @api.constrains('delivery_date')
    def _check_delivery_date_not_in_past(self):
        for record in self:
            if record.delivery_date and record.delivery_date < fields.Date.today():
                raise ValidationError(
                    _("Delivery Date cannot be earlier than today."))

    @api.model
    def _get_purchase_order_access_menu_code(self, vals=None):
        vals = vals or {}
        menu_code = vals.get('entry_menu_code') or self.env.context.get(
            'default_entry_menu_code') or self.env.context.get('access_menu_code')
        if menu_code:
            return menu_code

        params = self.env.context.get('params') or {}
        action_id = params.get('action')
        if not action_id and request:
            action_id = request.params.get('action')
        if action_id:
            try:
                action_id = int(action_id)
            except (TypeError, ValueError):
                action_id = False
        if action_id:
            if action_id == self.env.ref('purchases.purchases_rfq_action').id:
                return 'rfq'
            if action_id == self.env.ref('purchases.purchases_purchase_order_action').id:
                return 'purchase_order'

        state = vals.get('state') or self.env.context.get('default_state')
        if state in ('draft', 'wait_approval', 'approved', 'cancel'):
            return 'rfq'
        if state in ('sent', 'purchase'):
            return 'purchase_order'
        return self._menu_code

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)

        if self.env.user.has_group('base.group_system'):
            return res

        auth_model = self.env['general.auth'].sudo()
        context_menu_code = self.env.context.get(
            'access_menu_code') or self.env.context.get('default_entry_menu_code')
        requested_view_ids = {view_id for view_id, _view_type in (views or []) if view_id}
        if self.env.ref('purchases.purchases_rfq_tree').id in requested_view_ids:
            context_menu_code = 'rfq'
        elif self.env.ref('purchases.purchases_po_tree').id in requested_view_ids:
            context_menu_code = 'purchase_order'
        if not context_menu_code:
            params = self.env.context.get('params') or {}
            action_id = params.get('action')
            if not action_id and request:
                action_id = request.params.get('action')
            if action_id:
                try:
                    action_id = int(action_id)
                except (TypeError, ValueError):
                    action_id = False
            if action_id:
                if action_id == self.env.ref('purchases.purchases_rfq_action').id:
                    context_menu_code = 'rfq'
                elif action_id == self.env.ref('purchases.purchases_purchase_order_action').id:
                    context_menu_code = 'purchase_order'
        rfq_access = auth_model.search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', 'rfq')
        ], limit=1)
        po_access = auth_model.search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', 'purchase_order')
        ], limit=1)
        if context_menu_code == 'rfq':
            can_create_any_purchase_document = bool(
                rfq_access and rfq_access.can_create)
        elif context_menu_code == 'purchase_order':
            can_create_any_purchase_document = bool(
                po_access and po_access.can_create)
        else:
            can_create_any_purchase_document = (
                (rfq_access and rfq_access.can_create) or
                (po_access and po_access.can_create)
            )

        if not can_create_any_purchase_document:
            import lxml.etree as etree
            for view_type in ['list', 'form']:
                if view_type in res['views']:
                    doc = etree.fromstring(res['views'][view_type]['arch'])
                    doc.set('create', '0')
                    res['views'][view_type]['arch'] = etree.tostring(
                        doc, encoding='unicode')

        return res

    @api.model
    def create(self, vals):
        # RFQ/PO dibuat otomatis dari Sales (procurement) — jangan blokir dengan hak menu RFQ.
        if not self.env.context.get('skip_purchase_order_create_auth_check'):
            if not self.env.user.has_group('base.group_system'):
                auth_model = self.env['general.auth'].sudo()
                menu_code = self._get_purchase_order_access_menu_code(vals)
                access = auth_model.search([
                    ('custom_user_id.user_id', '=', self.env.uid),
                    ('menu_id.menu_id', '=', menu_code)
                ], limit=1)
                if not access or not access.can_create:
                    raise UserError(
                        _("You do not have access rights to create purchase orders."))

        if not vals.get('entry_menu_code'):
            vals['entry_menu_code'] = self._get_purchase_order_access_menu_code(vals)
        if not vals.get('po_code'):
            vals['po_code'] = self.env['ir.sequence'].next_by_code(
                'purchases.purchase_order') or '/'
        return super(purchase_order, self).create(vals)

    @api.depends('order_line_ids.sub_total', 'order_line_ids.tax_amount')
    def _compute_total_amount(self):
        for record in self:
            untaxed = sum(line.sub_total for line in record.order_line_ids)
            tax = sum(line.tax_amount for line in record.order_line_ids)
            record.total_amount_untaxed = untaxed
            record.total_tax = tax
            record.total_amount = untaxed + tax

    @api.depends('bill_ids.state')
    def _compute_bill_count(self):
        for record in self:
            record.bill_count = len(record.bill_ids.filtered(
                lambda b: b.state != 'cancel'))

    @api.depends('state', 'is_sent', 'bill_ids.state', 'receipt_status')
    def _compute_bill_status(self):
        for record in self:
            active_bills = record.bill_ids.filtered(
                lambda b: b.state != 'cancel')
            if active_bills.filtered(lambda b: b.state == 'posted'):
                record.bill_status = 'billed'
            elif record.state in ['purchase', 'approved'] and record.is_sent:
                record.bill_status = 'to_bill'
            else:
                record.bill_status = 'no'

    @api.depends('receipt_ids.state')
    def _compute_receipt_count(self):
        for record in self:
            record.receipt_count = len(record.receipt_ids.filtered(
                lambda r: r.state != 'cancel'))

    @api.depends('state', 'is_sent', 'order_line_ids.qty_received', 'order_line_ids.quantity', 'receipt_ids.state')
    def _compute_receipt_status(self):
        for record in self:
            active_receipts = record.receipt_ids.filtered(
                lambda r: r.state == 'received')
            if record.state not in ['purchase', 'approved'] or not record.is_sent:
                record.receipt_status = 'no'
                continue
            total_qty = sum(record.order_line_ids.mapped('quantity'))
            received_qty = sum(record.order_line_ids.mapped('qty_received'))
            if not active_receipts or received_qty <= 0:
                record.receipt_status = 'to_receive'
            elif total_qty and received_qty >= total_qty:
                record.receipt_status = 'received'
            else:
                record.receipt_status = 'partial'

    @api.depends('total_amount')
    def _compute_need_approval(self):
        matrix_model = self.env['purchases.purchase_approval_matrix'].sudo()
        for record in self:
            threshold = matrix_model.search(
                [('min_amount', '<', record.total_amount)],
                order='sequence asc', limit=1)
            record.need_approval = bool(threshold)

    @api.depends('approval_log_ids.state')
    def _compute_current_approver(self):
        for rec in self:
            pending_logs = rec.approval_log_ids.filtered(
                lambda l: l.state == 'pending'
            ).sorted('sequence')
            if pending_logs:
                rec.current_approver = pending_logs[0].user_id
                rec.current_approver_name = pending_logs[0].approver
            else:
                rec.current_approver = False
                rec.current_approver_name = False

    @api.depends('state', 'approval_log_ids')
    def _compute_approval_permissions(self):
        self.user_can_approve = False
        self.user_can_revise = False
        self.user_can_return = False
        self.user_can_reject = False

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)

        if current_custom_user:
            matrix_line = self.env['purchases.purchase_approval_matrix'].sudo().search([
                ('name', '=', current_custom_user.id)
            ], limit=1)
            if matrix_line:
                for rec in self:
                    rec.user_can_approve = matrix_line.approve
                    rec.user_can_revise = matrix_line.revise
                    rec.user_can_return = matrix_line.returned
                    rec.user_can_reject = matrix_line.reject

    def _compute_submit_permissions(self):
        self.user_can_submit = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_submit = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        submit_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_submit', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if submit_authorized:
            for rec in self:
                rec.user_can_submit = True

    def _compute_confirm_order_permissions(self):
        self.user_can_confirm_order = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_confirm_order = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        confirm_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_confirm', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if confirm_authorized:
            for rec in self:
                rec.user_can_confirm_order = True

    def _compute_cancel_order_permissions(self):
        self.user_can_cancel_order = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_cancel_order = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        auth_model = self.env['general.auth'].sudo()
        rfq_delete = auth_model.search([
            ('menu_id.menu_id', '=', 'rfq'),
            ('can_delete', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)
        po_delete = auth_model.search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_delete', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if rfq_delete or po_delete:
            for rec in self:
                rec.user_can_cancel_order = True

    def _compute_send_permissions(self):
        self.user_can_send = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_send = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        send_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_send', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if send_authorized:
            for rec in self:
                rec.user_can_send = True

    def _compute_receive_permissions(self):
        self.user_can_receive = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_receive = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        receive_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_receive', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if receive_authorized:
            for rec in self:
                rec.user_can_receive = True

    def _compute_update_permissions(self):
        self.user_can_update = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_update = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        update_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_update', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if update_authorized:
            for rec in self:
                rec.user_can_update = True

    def _compute_delete_permissions(self):
        self.user_can_delete = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_delete = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        delete_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_delete', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if delete_authorized:
            for rec in self:
                rec.user_can_delete = True

    def _compute_billing_permissions(self):
        self.user_can_billing = False
        if self.env.user.has_group('base.group_system'):
            for rec in self:
                rec.user_can_billing = True
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        billing_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_billing', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)

        if billing_authorized:
            for rec in self:
                rec.user_can_billing = True

    def action_send_po_by_email(self):
        self.ensure_one()
        if self.state not in ['purchase', 'approved']:
            raise UserError(_("Only confirmed or approved Purchase Orders can be sent by email."))

        # Cek permission
        if not self.env.user.has_group('base.group_system'):
            current_custom_user = self.env['general.custom_users'].sudo().search([
                ('user_id', '=', self.env.uid)
            ], limit=1)
            send_authorized = self.env['general.auth'].sudo().search([
                ('menu_id.menu_id', '=', 'purchase_order'),
                ('can_send', '=', True),
                ('custom_user_id', '=',
                 current_custom_user.id if current_custom_user else None)
            ], limit=1)
            if not send_authorized:
                raise UserError(_("You do not have access rights to send purchase orders by email."))

        template = self.env.ref(
            'purchases.email_template_purchase_order', raise_if_not_found=False)

        # Generate PDF attachment
        attachment_ids = []
        try:
            pdf_content, _mime = self.env['ir.actions.report']._render_qweb_pdf(
                'purchases.action_report_purchase_order', [self.id])
            filename = 'PO - %s.pdf' % self.po_code

            # Hapus attachment lama dengan nama yang sama agar tidak duplikat
            old_attachments = self.env['ir.attachment'].sudo().search([
                ('name', '=', filename),
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
            ])
            if old_attachments:
                old_attachments.sudo().unlink()

            attachment = self.env['ir.attachment'].sudo().create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            attachment_ids = [attachment.id]
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Failed to generate PO PDF attachment: %s", e)

        # Tentukan email_from
        email_from = False
        if self.buyer_id and self.buyer_id.user_id:
            buyer_user = self.buyer_id.user_id
            email_from = buyer_user.email or buyer_user.login or False
        if not email_from:
            current_user = self.env.user
            email_from = current_user.email or current_user.login or False
        if not email_from:
            email_from = self.env.company.email or False

        if not email_from:
            raise UserError(_(
                "Tidak dapat mengirim email: alamat email pengirim belum dikonfigurasi. "
                "Harap isi email pada profil buyer, akun pengguna Anda, atau email perusahaan."
            ))

        # Sync email vendor ke partner jika perlu
        if self.vendor_id and self.vendor_id.partner_id:
            partner = self.vendor_id.partner_id
            if self.vendor_id.email and partner.email != self.vendor_id.email:
                partner.sudo().write({'email': self.vendor_id.email})

        # Kumpulkan vendor dan partner_id-nya sebagai recipient
        vendor_ids = [self.vendor_id.id] if self.vendor_id else []
        partner_ids = [self.vendor_id.partner_id.id] if self.vendor_id and self.vendor_id.partner_id else []

        ctx = {
            'default_model': 'purchases.purchase_order',
            'default_res_ids': [self.id],
            'default_use_template': bool(template),
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'default_attachment_ids': [(6, 0, attachment_ids)],
            'default_email_from': email_from,
            'default_vendor_ids': [(6, 0, vendor_ids)],
            'default_partner_ids': [(6, 0, partner_ids)],
            'redirect_to_tree': 'purchases.purchases_purchase_order_action',
            'show_email_in_wizard': True,
        }

        # Tandai is_sent secara permanen tanpa mengubah state
        self.write({'is_sent': True})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Purchase Order by Email'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def _check_confirm_order_access(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        confirm_authorized = self.env['general.auth'].sudo().search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_confirm', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)
        if not confirm_authorized:
            raise UserError(
                _("You do not have access rights to confirm purchase orders."))

    def _check_cancel_order_access(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            return

        current_custom_user = self.env['general.custom_users'].sudo().search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        auth_model = self.env['general.auth'].sudo()
        rfq_delete = auth_model.search([
            ('menu_id.menu_id', '=', 'rfq'),
            ('can_delete', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)
        po_delete = auth_model.search([
            ('menu_id.menu_id', '=', 'purchase_order'),
            ('can_delete', '=', True),
            ('custom_user_id', '=',
             current_custom_user.id if current_custom_user else None)
        ], limit=1)
        if not (rfq_delete or po_delete):
            raise UserError(
                _("You do not have access rights to cancel purchase orders."))

    @api.onchange('vendor_id')
    def _onchange_vendor_id(self):
        if self.vendor_id:
            self.payment_terms = self.vendor_id.payment_terms
        else:
            self.payment_terms = False

    def action_confirm_order(self):
        self.ensure_one()
        self._check_confirm_order_access()
        if not self.order_line_ids:
            raise UserError(
                _("Please add at least one order line before confirming the order."))
        self.write({
            'state': 'purchase',
            'entry_menu_code': 'purchase_order',
        })
        # Buat approval logs jika butuh approval (state tetap purchase)
        self._check_approval_requirement()

    def action_submit_rfq(self):
        """Ubah status RFQ dari Draft menjadi Sent (RFQ Sent)."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft RFQs can be submitted."))
        if not self.order_line_ids:
            raise UserError(
                _("Please add at least one order line before submitting."))
        self.state = 'sent'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': {**self.env.context},
        }

    def action_cancel(self):
        self.ensure_one()
        self._check_cancel_order_access()
        if self.state not in ['draft', 'sent', 'purchase', 'approved']:
            raise UserError(_("Only draft, RFQ, confirmed, or approved purchase orders can be cancelled."))
        if self.state == 'purchase':
            # Cek permission delete untuk cancel dari state purchase
            if not self.env.user.has_group('base.group_system'):
                current_custom_user = self.env['general.custom_users'].sudo().search([
                    ('user_id', '=', self.env.uid)
                ], limit=1)
                delete_authorized = self.env['general.auth'].sudo().search([
                    ('menu_id.menu_id', '=', 'purchase_order'),
                    ('can_delete', '=', True),
                    ('custom_user_id', '=',
                     current_custom_user.id if current_custom_user else None)
                ], limit=1)
                if not delete_authorized:
                    raise UserError(_("You do not have access rights to cancel confirmed purchase orders."))
        self.state = 'cancel'
        return self.action_back_to_orders()

    def action_reset_to_draft(self):
        self.ensure_one()
        self.approval_status = 'pending'
        self.state = 'draft'

    def write(self, vals):
        res = super(purchase_order, self).write(vals)
        return res

    def _check_approval_requirement(self):
        """Dipanggil setelah PO di-confirm. Jika total_amount melebihi threshold matrix,
        buat approval logs. State tetap purchase — user harus Submit for Approval secara manual."""
        matrix_model = self.env['purchases.purchase_approval_matrix'].sudo()
        for record in self:
            threshold = matrix_model.search(
                [('min_amount', '<', record.total_amount)],
                order='sequence asc', limit=1)
            if threshold:
                # Hapus pending logs lama jika ada
                existing_pending = record.approval_log_ids.filtered(
                    lambda log: log.state == 'pending')
                if existing_pending:
                    existing_pending.unlink()

                max_sequence = matrix_model.search(
                    [('min_amount', '>', record.total_amount)],
                    order='sequence asc', limit=1).sequence

                if max_sequence:
                    matrix_data = matrix_model.search(
                        [('sequence', '<', max_sequence)], order='sequence asc')
                else:
                    matrix_data = matrix_model.search([], order='sequence asc')

                log_lines = []
                for index, matrix in enumerate(matrix_data):
                    vals = {
                        'user_id': matrix.name.user_id.id if matrix.name.user_id else None,
                        'approver': matrix.name.name,
                        'email': matrix.name.user_id.login if matrix.name.user_id else '',
                        'position': matrix.position.position_name if matrix.position else '',
                        'sequence': matrix.sequence,
                        'min_amount': matrix.min_amount,
                        'receive_return': matrix.receive_return,
                        'approve': matrix.approve,
                        'revise': matrix.revise,
                        'returned': matrix.returned,
                        'reject': matrix.reject,
                        'notify': matrix.notify,
                        'approved_as': matrix.approved_as,
                        'state': 'pending',
                    }
                    if index == 0:
                        vals['approval_reason'] = _(
                            "Total amount %(total)s exceeds the minimum threshold of %(threshold)s for approval."
                        ) % {
                            'total': f"{record.total_amount:,.0f}",
                            'threshold': f"{threshold.min_amount:,.0f}",
                        }
                    log_lines.append((0, 0, vals))

                if log_lines:
                    super(purchase_order, record).write({
                        'approval_log_ids': log_lines,
                        'approval_status': 'pending',
                        # State tetap purchase — tidak otomatis ke wait_approval
                    })

    def action_submit_for_approval(self):
        self.ensure_one()
        if self.state != 'purchase':
            raise UserError(
                _("Only confirmed purchase orders can be submitted for approval."))
        if not self.need_approval:
            raise UserError(
                _("This purchase order does not require approval."))
        # Pastikan approval logs sudah terisi sebelum submit
        pending_logs = self.approval_log_ids.filtered(lambda l: l.state == 'pending')
        if not pending_logs:
            self._check_approval_requirement()
        self.state = 'wait_approval'
        self._send_approval_notification()

    def _send_approval_notification(self):
        """Kirim email notifikasi ke approver berikutnya yang pending."""
        self.ensure_one()
        template = self.env.ref(
            'purchases.email_template_purchase_approval_request', raise_if_not_found=False)
        if not template:
            return
        next_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending'
        ).sorted('sequence')
        if next_log:
            log = next_log[0]
            if log.email:
                ctx = {
                    'email_to': log.email,
                    'approver_name': log.approver,
                    'position': log.position,
                }
                template.with_context(ctx).send_mail(self.id, force_send=True)
                log.sudo().write({'mail_sent': True})

    def action_approve(self):
        self.ensure_one()
        if self.state != 'wait_approval':
            raise UserError(
                _("Only purchase orders in 'Waiting Approval' state can be approved."))
        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending'
        ).sorted('sequence')
        if not current_log or current_log[0].user_id != self.env.uid:
            raise UserError(
                _("You are not authorized to approve this document at this stage."))
        return {
            'name': _('Confirmation of Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id},
        }

    def action_approve_final(self):
        self.ensure_one()
        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.state == 'pending'
        ).sorted('sequence')
        if current_log:
            log = current_log[0]
            if log.user_id != self.env.uid:
                raise UserError(
                    _("You are not authorized to approve this document at this stage."))
            log.write({
                'state': 'approved',
                'action_date': fields.Datetime.now(),
            })
        if not self.approval_log_ids.sudo().filtered(lambda l: l.state == 'pending'):
            # Semua approved — set state ke approved
            self.write({
                'state': 'approved',
                'approval_status': 'approved',
            })
        else:
            # Masih ada pending — kirim notifikasi ke approver berikutnya
            self._send_approval_notification()
        return self.action_back_to_approvals()

    def action_revise(self):
        self.ensure_one()
        if self.state != 'wait_approval':
            raise UserError(
                _("Only purchase orders in 'Waiting Approval' state can be revised."))
        self.is_edit = True
        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': {'is_approval_view': True},
        }

    def action_save_revised(self):
        self.ensure_one()
        return {
            'name': _('Revise Message'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.revise.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id},
        }

    def action_return(self):
        self.ensure_one()
        if self.state != 'wait_approval':
            raise UserError(
                _("Only purchase orders in 'Waiting Approval' state can be returned."))
        return {
            'name': _('Please Provide Return Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id},
        }

    def action_reject(self):
        self.ensure_one()
        if self.state != 'wait_approval':
            raise UserError(
                _("Only purchase orders in 'Waiting Approval' state can be rejected."))
        return {
            'name': _('Please Provide Reject Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id},
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
        current_log.write({
            'state': 'rejected',
            'action_date': fields.Datetime.now(),
            'note': reason,
        })
        self.write({
            'state': 'cancel',
            'approval_status': 'rejected',
        })
        return self.action_back_to_approvals()

    def _approval_log_vals_from_matrix(self, matrix, state='pending', extra_vals=None):
        extra_vals = extra_vals or {}
        vals = {
            'purchase_order_id': self.id,
            'user_id': matrix.name.user_id.id if matrix.name and matrix.name.user_id else None,
            'approver': matrix.name.name if matrix.name else '',
            'email': matrix.name.user_id.login if matrix.name and matrix.name.user_id else '',
            'position': matrix.position.position_name if matrix.position else '',
            'sequence': matrix.sequence,
            'min_amount': matrix.min_amount,
            'receive_return': matrix.receive_return,
            'approve': matrix.approve,
            'revise': matrix.revise,
            'returned': matrix.returned,
            'reject': matrix.reject,
            'notify': matrix.notify,
            'approved_as': matrix.approved_as,
            'state': state,
        }
        vals.update(extra_vals)
        return vals

    def _rebuild_approval_logs_after_revise(self, reviser_sequence):
        """Hapus semua log pending, lalu buat ulang dari matrix (sequence >= reviser)."""
        self.ensure_one()
        matrix_model = self.env['purchases.purchase_approval_matrix'].sudo()

        self.approval_log_ids.filtered(lambda l: l.state == 'pending').unlink()

        domain = [('sequence', '>=', reviser_sequence)]
        max_seq_rec = matrix_model.search(
            [('min_amount', '>', self.total_amount)], order='sequence asc', limit=1)
        if max_seq_rec:
            domain.append(('sequence', '<', max_seq_rec.sequence))

        approvers = matrix_model.search(domain, order='sequence asc')
        for approver in approvers:
            self.approval_log_ids.create(
                self._approval_log_vals_from_matrix(approver))

        if approvers:
            self._send_approval_notification()

    def action_revise_final(self):
        self.ensure_one()
        message = self.env.context.get('revise_message')
        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.user_id == self.env.uid and l.state == 'pending'
        )
        if not current_log:
            raise UserError(
                _("You are not authorized to revise this document."))
        self.is_edit = False
        reviser_sequence = current_log[0].sequence
        current_log.write({
            'state': 'revised',
            'action_date': fields.Datetime.now(),
            'note': message,
        })
        self._rebuild_approval_logs_after_revise(reviser_sequence)
        return self.action_view_purchase_order(approval_view=True)

    def action_return_final(self):
        self.ensure_one()
        reason = self.env.context.get('return_reason')
        current_log = self.approval_log_ids.sudo().filtered(
            lambda l: l.user_id == self.env.uid and l.state == 'pending'
        )
        if not current_log:
            raise UserError(
                _("You are not authorized to return this document."))
        returner_sequence = current_log[0].sequence
        current_log.write({
            'state': 'returned',
            'action_date': fields.Datetime.now(),
            'note': reason,
        })
        self.approval_log_ids.filtered(lambda l: l.state == 'pending').unlink()

        matrix_model = self.env['purchases.purchase_approval_matrix'].sudo()
        return_matrix = matrix_model.search([
            ('receive_return', '=', True),
            ('sequence', '<', returner_sequence),
        ], order='sequence asc', limit=1)

        if return_matrix:
            domain = [('sequence', '>=', return_matrix.sequence)]
            max_seq_rec = matrix_model.search(
                [('min_amount', '>', self.total_amount)], order='sequence asc', limit=1)
            if max_seq_rec:
                domain.append(('sequence', '<', max_seq_rec.sequence))
            approvers = matrix_model.search(domain, order='sequence asc')
            for approver in approvers:
                self.approval_log_ids.create(
                    self._approval_log_vals_from_matrix(approver))
            self.write({'state': 'wait_approval', 'approval_status': 'pending'})
            self._send_approval_notification()
        else:
            self.approval_log_ids.filtered(lambda l: l.state == 'pending').unlink()
            self.write({'state': 'purchase', 'approval_status': 'pending'})
        return self.action_back_to_approvals()

    def action_create_bill(self):
        self.ensure_one()
        if self.state not in ['purchase', 'approved']:
            raise UserError(
                _("Bill can only be created from a confirmed purchase order."))
        draft_bill = self.bill_ids.filtered(lambda b: b.state == 'draft')[:1]
        if draft_bill:
            return draft_bill.action_view_bill()
        bill = self.env['purchases.bill'].create(
            self._prepare_bill_vals())
        return bill.action_view_bill()

    def _prepare_bill_vals(self):
        self.ensure_one()
        line_vals = []
        for line in self.order_line_ids:
            tax_pct = line.taxes.tax_percentage if line.taxes else 0.0
            line_vals.append((0, 0, {
                'purchase_order_line_id': line.id,
                'product_id': line.product_id.id,
                'description': line.product_id.product_name if line.product_id else self.po_code,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'tax_id': line.taxes.id if line.taxes else False,
                'tax_percentage': tax_pct,
            }))
        return {
            'purchase_order_id': self.id,
            'vendor_id': self.vendor_id.id,
            'vendor_address': self.vendor_address,
            'bill_date': fields.Date.today(),
            'payment_terms_id': self.payment_terms.id if self.payment_terms else False,
            'buyer_id': self.buyer_id.id if self.buyer_id else False,
            'line_ids': line_vals,
        }

    def action_view_bills(self):
        self.ensure_one()
        active_bills = self.bill_ids.filtered(lambda b: b.state != 'cancel')
        if len(active_bills) == 1:
            return active_bills.action_view_bill()
        return {
            'name': _('Bills'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.bill',
            'view_mode': 'tree,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'target': 'current',
        }

    def action_create_receipt(self):
        self.ensure_one()
        if self.state not in ['purchase', 'approved']:
            raise UserError(
                _("Receipt can only be created from a confirmed purchase order."))
        remaining_lines = self.order_line_ids.filtered(
            lambda line: line.qty_to_receive > 0)
        if not remaining_lines:
            raise UserError(
                _("All products on this purchase order have already been received."))
        draft_receipt = self.receipt_ids.filtered(
            lambda r: r.state == 'draft')[:1]
        if draft_receipt:
            return draft_receipt.action_view_receipt()
        receipt = self.env['purchases.receipt'].with_context(
            allow_internal_receipt_create=True
        ).create(
            self._prepare_receipt_vals())
        return receipt.action_view_receipt()

    def _prepare_receipt_vals(self):
        self.ensure_one()
        line_vals = []
        for line in self.order_line_ids.filtered(lambda l: l.qty_to_receive > 0):
            line_vals.append((0, 0, {
                'purchase_order_line_id': line.id,
                'product_id': line.product_id.id,
                'description': line.description or (line.product_id.product_name if line.product_id else self.po_code),
                'ordered_qty': line.quantity,
                'quantity': line.qty_to_receive,
            }))
        return {
            'purchase_order_id': self.id,
            'vendor_id': self.vendor_id.id,
            'receipt_date': fields.Date.today(),
            'buyer_id': self.buyer_id.id if self.buyer_id else False,
            'line_ids': line_vals,
        }

    def action_view_receipts(self):
        self.ensure_one()
        active_receipts = self.receipt_ids.filtered(
            lambda r: r.state != 'cancel')
        if len(active_receipts) == 1:
            return active_receipts.action_view_receipt()
        return {
            'name': _('Receipts'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.receipt',
            'view_mode': 'tree,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'target': 'current',
        }

    def action_view_purchase_order(self, approval_view=False):
        self.ensure_one()
        ctx = {
            **self.env.context,
            'is_approval_view': approval_view or self.env.context.get('is_approval_view'),
            'create': False,
        }
        if self.entry_menu_code:
            ctx['access_menu_code'] = self.entry_menu_code
            ctx['default_entry_menu_code'] = self.entry_menu_code
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'res_model': 'purchases.purchase_order',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': ctx,
        }

    def action_back_to_rfq(self):
        self.ensure_one()
        rfq_tree = self.env.ref('purchases.purchases_rfq_tree', raise_if_not_found=False)
        return {
            'name': 'Requests for Quotation',
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.purchase_order',
            'view_mode': 'tree,form',
            'views': [(rfq_tree.id if rfq_tree else False, 'tree'), (False, 'form')],
            'target': 'main',
            'domain': [('state', 'in', ['draft', 'sent', 'cancel'])],
            'context': {'default_state': 'draft', 'access_menu_code': 'rfq', 'default_entry_menu_code': 'rfq'},
        }

    def action_back_to_orders(self):
        self.ensure_one()
        po_tree = self.env.ref('purchases.purchases_po_tree', raise_if_not_found=False)
        return {
            'name': 'Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.purchase_order',
            'view_mode': 'tree,form',
            'views': [(po_tree.id if po_tree else False, 'tree'), (False, 'form')],
            'target': 'main',
            'domain': [('state', 'in', ['sent', 'purchase', 'wait_approval', 'approved', 'cancel'])],
            'context': {'access_menu_code': 'purchase_order', 'default_entry_menu_code': 'purchase_order'},
        }

    def action_back_from_rfq(self):
        """Kembali ke RFQ tree — dipanggil saat user datang dari menu RFQ."""
        self.ensure_one()
        rfq_tree = self.env.ref('purchases.purchases_rfq_tree', raise_if_not_found=False)
        return {
            'name': 'Requests for Quotation',
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.purchase_order',
            'view_mode': 'tree,form',
            'views': [(rfq_tree.id if rfq_tree else False, 'tree'), (False, 'form')],
            'target': 'main',
            'domain': [('state', 'in', ['draft', 'sent', 'cancel'])],
            'context': {'default_state': 'draft', 'access_menu_code': 'rfq', 'default_entry_menu_code': 'rfq'},
        }

    def action_back_to_approvals(self):
        self.ensure_one()
        return {
            'name': 'Waiting My Approval',
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.purchase_order',
            'view_mode': 'tree,form',
            'target': 'main',
            'domain': [('current_approver', '=', self.env.uid), ('state', 'in', ['wait_approval'])],
            'context': {'search_default_filter_to_approve': 1, 'create': False, 'is_approval_view': True},
        }


class purchase_order_line(models.Model):
    _name = 'purchases.purchase_order_line'
    _description = 'Purchase Order Line'

    purchase_order_id = fields.Many2one(
        comodel_name='purchases.purchase_order', string='Purchase Order',
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product',
        ondelete='set null', index=True,
        domain=[('purchase_ok', '=', True)])
    description = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity", default=1.0)
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM")
    unit_price = fields.Float(string="Unit Price", digits=(16, 0))
    taxes = fields.Many2one(
        comodel_name='sales.taxes', string="Taxes",
        ondelete='set null', index=True,
        default=lambda self: self.env['sales.taxes'].search([('default_tax', '=', True)], limit=1))
    tax_percentage = fields.Float(
        related='taxes.tax_percentage', string="Tax %", store=True)

    def init(self):
        """Drop stale FK to purchases_taxes if it still exists after model migration."""
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name = 'purchases_purchase_order_line_taxes_fkey'
                      AND table_name = 'purchases_purchase_order_line'
                ) THEN
                    ALTER TABLE purchases_purchase_order_line
                        DROP CONSTRAINT purchases_purchase_order_line_taxes_fkey;
                END IF;
            END$$;
        """)
    sub_total = fields.Float(
        string="Sub Total", compute='_compute_amounts',
        store=True, digits=(16, 0))
    tax_amount = fields.Float(
        string="Tax Amount", compute='_compute_amounts',
        store=True, digits=(16, 0))
    qty_received = fields.Float(
        string="Received Qty", default=0.0, digits=(16, 2))
    qty_to_receive = fields.Float(
        string="Qty to Receive", compute='_compute_qty_to_receive',
        store=True, digits=(16, 2))

    @api.depends('quantity', 'unit_price', 'tax_percentage')
    def _compute_amounts(self):
        for record in self:
            record.sub_total = record.quantity * record.unit_price
            record.tax_amount = record.sub_total * \
                (record.tax_percentage / 100.0)

    @api.depends('quantity', 'qty_received')
    def _compute_qty_to_receive(self):
        for record in self:
            record.qty_to_receive = max(
                record.quantity - record.qty_received, 0.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.product_name
            self.unit_price = self.product_id.price
            self.taxes = self.env['sales.taxes'].search(
                [('default_tax', '=', True)], limit=1)


# ─────────────────────────────────────────────
#  BILL (Vendor Invoice)
# ─────────────────────────────────────────────

class bill(models.Model):
    _name = 'purchases.bill'
    _inherit = ['purchases.edit.mixin']
    _description = 'Vendor Bill'
    _rec_name = 'bill_number'
    _order = 'bill_number desc, id desc'
    _menu_code = 'vendor_bills'

    bill_number = fields.Char(string="Bill Number", readonly=True, copy=False)
    purchase_order_id = fields.Many2one(
        comodel_name='purchases.purchase_order', string='Purchase Order',
        ondelete='restrict', index=True, required=True)
    vendor_id = fields.Many2one(
        comodel_name='purchases.vendor', string='Vendor',
        ondelete='restrict', index=True, required=True)
    vendor_address = fields.Text(string="Vendor Address")
    buyer_id = fields.Many2one(
        comodel_name='general.custom_users', string='Buyer',
        ondelete='set null', index=True)
    bill_date = fields.Date(
        string="Bill Date", default=fields.Date.today, required=True)
    due_date = fields.Date(string="Due Date")
    payment_terms_id = fields.Many2one(
        comodel_name='sales.payment_terms', string='Payment Terms',
        ondelete='set null', index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    posted_date = fields.Datetime(
        string="Posted On", readonly=True, copy=False)
    line_ids = fields.One2many(
        'purchases.bill.line', 'bill_id', string='Bill Lines')
    amount_untaxed = fields.Float(
        string="Untaxed Amount", compute='_compute_amounts',
        store=True, digits=(16, 0))
    amount_tax = fields.Float(
        string="Tax Amount", compute='_compute_amounts',
        store=True, digits=(16, 0))
    amount_total = fields.Float(
        string="Total", compute='_compute_amounts',
        store=True, digits=(16, 0))
    amount_paid = fields.Float(
        string="Amount Paid", default=0.0, digits=(16, 0))
    amount_due = fields.Float(
        string="Amount Due", compute='_compute_payment_state',
        store=True, digits=(16, 0))
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ], string="Payment Status", compute='_compute_payment_state',
        store=True, default='not_paid')
    note = fields.Text(string="Notes")

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)

        if self.env.user.has_group('base.group_system'):
            return res

        access = self.env['general.auth'].sudo().search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', self._menu_code)
        ], limit=1)

        if not access or not access.can_create:
            import lxml.etree as etree
            for view_type in ['list', 'form']:
                if view_type in res['views']:
                    doc = etree.fromstring(res['views'][view_type]['arch'])
                    doc.set('create', '0')
                    res['views'][view_type]['arch'] = etree.tostring(
                        doc, encoding='unicode')

        return res

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('base.group_system'):
            # Cek can_billing di menu purchase_order
            billing_access = self.env['general.auth'].sudo().search([
                ('custom_user_id.user_id', '=', self.env.uid),
                ('menu_id.menu_id', '=', 'purchase_order'),
                ('can_billing', '=', True),
            ], limit=1)
            # Fallback: cek can_create di menu vendor_bills
            if not billing_access:
                create_access = self.env['general.auth'].sudo().search([
                    ('custom_user_id.user_id', '=', self.env.uid),
                    ('menu_id.menu_id', '=', self._menu_code),
                    ('can_create', '=', True),
                ], limit=1)
                if not create_access:
                    raise UserError(
                        _("You do not have access rights to create vendor bills."))
        for vals in vals_list:
            if not vals.get('bill_number'):
                vals['bill_number'] = self.env['ir.sequence'].next_by_code(
                    'purchases.bill') or '/'
        return super(bill, self).create(vals_list)

    @api.depends('line_ids.sub_total', 'line_ids.tax_amount')
    def _compute_amounts(self):
        for record in self:
            record.amount_untaxed = sum(record.line_ids.mapped('sub_total'))
            record.amount_tax = sum(record.line_ids.mapped('tax_amount'))
            record.amount_total = record.amount_untaxed + record.amount_tax

    @api.depends('amount_total', 'amount_paid', 'state')
    def _compute_payment_state(self):
        for record in self:
            if record.state != 'posted' or record.amount_total <= 0:
                record.payment_state = 'not_paid'
                record.amount_due = record.amount_total
            elif record.amount_paid <= 0:
                record.payment_state = 'not_paid'
                record.amount_due = record.amount_total
            elif record.amount_paid >= record.amount_total:
                record.payment_state = 'paid'
                record.amount_due = 0.0
            else:
                record.payment_state = 'partial'
                record.amount_due = record.amount_total - record.amount_paid

    def action_register_payment(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_("Only posted bills can be paid."))
        if self.payment_state == 'paid':
            raise UserError(_("This bill has already been fully paid."))
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bill_id': self.id,
                'default_amount': self.amount_due,
                'default_partner_name': self.vendor_id.vendor_name if self.vendor_id else '',
            },
        }

    def action_post(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft bills can be confirmed."))
        if not self.line_ids:
            raise UserError(
                _("Please add at least one line before confirming."))
        self.write({
            'state': 'posted',
            'posted_date': fields.Datetime.now(),
        })
        return self.action_view_bill()

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'posted':
            raise UserError(
                _("Posted bills cannot be cancelled directly. Reset to draft first."))
        self.state = 'cancel'
        return self.action_back_to_bills()

    def action_reset_to_draft(self):
        self.ensure_one()
        self.state = 'draft'
        return self.action_view_bill()

    def action_view_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Bill',
            'res_model': 'purchases.bill',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_open_purchase_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'res_model': 'purchases.purchase_order',
            'view_mode': 'form',
            'res_id': self.purchase_order_id.id,
            'target': 'current',
        }

    def action_back_to_bills(self):
        self.ensure_one()
        return {
            'name': 'Vendor Bills',
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.bill',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'context': self.env.context,
        }


class PaymentRegisterWizard(models.TransientModel):
    _name = 'purchases.payment.register'
    _description = 'Register Payment for Vendor Bill'

    bill_id = fields.Many2one(
        'purchases.bill', string='Bill', required=True, ondelete='cascade')
    bill_number = fields.Char(
        related='bill_id.bill_number', string='Bill Number', readonly=True)
    vendor_name = fields.Char(
        string='Vendor', readonly=True)
    amount_total = fields.Float(
        related='bill_id.amount_total', string='Bill Total', readonly=True, digits=(16, 0))
    amount_paid_before = fields.Float(
        related='bill_id.amount_paid', string='Already Paid', readonly=True, digits=(16, 0))
    amount = fields.Float(
        string='Payment Amount', required=True, digits=(16, 0))
    payment_date = fields.Date(
        string='Payment Date', required=True, default=fields.Date.today)
    memo = fields.Char(string='Memo')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Payment amount must be greater than zero."))
            if rec.amount > rec.bill_id.amount_due:
                raise ValidationError(_(
                    "Payment amount (%(amount)s) cannot exceed the amount due (%(due)s)."
                ) % {
                    'amount': f"{rec.amount:,.0f}",
                    'due': f"{rec.bill_id.amount_due:,.0f}",
                })

    def action_confirm_payment(self):
        self.ensure_one()
        bill = self.bill_id
        new_paid = bill.amount_paid + self.amount
        bill.write({'amount_paid': new_paid})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payment Registered'),
                'message': _(
                    'Payment of %(amount)s has been registered for %(bill)s.'
                ) % {
                    'amount': f"Rp {self.amount:,.0f}",
                    'bill': bill.bill_number,
                },
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class bill_line(models.Model):
    _name = 'purchases.bill.line'
    _description = 'Vendor Bill Line'
    _order = 'id'

    bill_id = fields.Many2one(
        comodel_name='purchases.bill', string='Bill',
        ondelete='cascade', index=True, required=True)
    purchase_order_line_id = fields.Many2one(
        comodel_name='purchases.purchase_order_line', string='PO Line',
        ondelete='set null', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product',
        ondelete='set null', index=True)
    description = fields.Char(string="Description", required=True)
    quantity = fields.Float(string="Quantity", default=1.0)
    unit_price = fields.Float(string="Unit Price", digits=(16, 0), default=0.0)
    tax_id = fields.Many2one(
        comodel_name='sales.taxes', string='Tax',
        ondelete='set null', index=True)
    tax_percentage = fields.Float(string="Tax %", default=0.0)
    sub_total = fields.Float(
        string="Sub Total", compute='_compute_amounts',
        store=True, digits=(16, 0))
    tax_amount = fields.Float(
        string="Tax Amount", compute='_compute_amounts',
        store=True, digits=(16, 0))
    total = fields.Float(
        string="Total", compute='_compute_amounts',
        store=True, digits=(16, 0))

    @api.depends('quantity', 'unit_price', 'tax_percentage')
    def _compute_amounts(self):
        for record in self:
            record.sub_total = record.quantity * record.unit_price
            record.tax_amount = record.sub_total * \
                (record.tax_percentage / 100.0)
            record.total = record.sub_total + record.tax_amount

    @api.onchange('tax_id')
    def _onchange_tax_id(self):
        self.tax_percentage = self.tax_id.tax_percentage if self.tax_id else 0.0


class purchase_approval_matrix(models.Model):
    _name = 'purchases.purchase_approval_matrix'
    _inherit = ['purchases.edit.mixin']
    _description = 'Purchase Approval Matrix'
    _order = 'sequence asc'

    name = fields.Many2one(
        comodel_name='general.custom_users', string='Approver', index=True)
    sequence = fields.Integer(string="Sequence", default=1)
    position = fields.Many2one(related='name.position', string="Job Position")
    receive_return = fields.Boolean(string="Receive Return")
    min_amount = fields.Float(string="Minimum Amount",
                              digits=(16, 0), default=0)
    approve = fields.Boolean(string="Allow Approve", default=False)
    revise = fields.Boolean(string="Allow Revision", default=False)
    returned = fields.Boolean(string="Allow Return", default=False)
    reject = fields.Boolean(string="Allow Reject", default=False)
    notify = fields.Boolean(string="Receive Notification", default=False)
    approved_as = fields.Selection([
        ('proposer', 'Proposer'),
        ('checker', 'Checker'),
        ('approver', 'Approver'),
        ('validator', 'Validator'),
        ('finalizer', 'Finalizer')
    ], string="Role in Approval", default='approver')


class purchase_approval_log(models.Model):
    _name = 'purchases.purchase_approval_log'
    _description = 'Purchase Approval Log'
    _order = 'id asc'

    purchase_order_id = fields.Many2one(
        comodel_name='purchases.purchase_order', string='Purchase Order',
        ondelete='cascade', index=True)
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
    notify = fields.Boolean(string="Notify", default=False)
    approved_as = fields.Char(string="Role in Approval")


class receipt(models.Model):
    _name = 'purchases.receipt'
    _inherit = ['purchases.edit.mixin']
    _description = 'Purchase Receipt'
    _rec_name = 'receipt_number'
    _order = 'receipt_number desc, id desc'
    _menu_code = 'purchase_receipts'

    receipt_number = fields.Char(
        string="Receipt Number", readonly=True, copy=False)
    purchase_order_id = fields.Many2one(
        comodel_name='purchases.purchase_order', string='Purchase Order',
        ondelete='restrict', index=True, required=True)
    vendor_id = fields.Many2one(
        comodel_name='purchases.vendor', string='Vendor',
        ondelete='restrict', index=True, required=True)
    buyer_id = fields.Many2one(
        comodel_name='general.custom_users', string='Buyer',
        ondelete='set null', index=True)
    receipt_date = fields.Date(
        string="Receipt Date", default=fields.Date.today, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft')
    received_date = fields.Datetime(
        string="Received On", readonly=True, copy=False)
    line_ids = fields.One2many(
        'purchases.receipt.line', 'receipt_id', string='Receipt Lines')
    note = fields.Text(string="Notes")

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)

        if self.env.user.has_group('base.group_system'):
            return res

        access = self.env['general.auth'].sudo().search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', self._menu_code)
        ], limit=1)

        if not access or not access.can_create:
            import lxml.etree as etree
            for view_type in ['list', 'form']:
                if view_type in res['views']:
                    doc = etree.fromstring(res['views'][view_type]['arch'])
                    doc.set('create', '0')
                    res['views'][view_type]['arch'] = etree.tostring(
                        doc, encoding='unicode')

        return res

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('base.group_system'):
            auth_model = self.env['general.auth'].sudo()
            if self.env.context.get('allow_internal_receipt_create'):
                receive_access = auth_model.search([
                    ('custom_user_id.user_id', '=', self.env.uid),
                    ('menu_id.menu_id', '=', 'purchase_order'),
                    ('can_receive', '=', True),
                ], limit=1)
                if not receive_access:
                    raise UserError(
                        _("You do not have access rights to receive products."))
            else:
                access = auth_model.search([
                    ('custom_user_id.user_id', '=', self.env.uid),
                    ('menu_id.menu_id', '=', self._menu_code)
                ], limit=1)
                if not access or not access.can_create:
                    raise UserError(
                        _("You do not have access rights to create receipts."))
        for vals in vals_list:
            if not vals.get('receipt_number'):
                vals['receipt_number'] = self.env['ir.sequence'].next_by_code(
                    'purchases.receipt') or '/'
        return super(receipt, self).create(vals_list)

    def action_receive(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft receipts can be validated."))
        if not self.line_ids:
            raise UserError(
                _("Please add at least one line before validating the receipt."))
        for line in self.line_ids:
            if line.quantity <= 0:
                raise UserError(
                    _("Received quantity must be greater than zero."))
            if line.purchase_order_line_id and line.quantity > line.purchase_order_line_id.qty_to_receive:
                raise UserError(
                    _("Received quantity cannot exceed the remaining quantity to receive."))
        for line in self.line_ids:
            if line.product_id:
                line.product_id.sudo().write({
                    'stock': line.product_id.stock + line.quantity
                })
            if line.purchase_order_line_id:
                line.purchase_order_line_id.write({
                    'qty_received': line.purchase_order_line_id.qty_received + line.quantity
                })
        self.write({
            'state': 'received',
            'received_date': fields.Datetime.now(),
        })
        return self.action_view_receipt()

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'received':
            raise UserError(
                _("Received receipts cannot be cancelled directly."))
        self.state = 'cancel'
        return self.action_back_to_receipts()

    def action_reset_to_draft(self):
        self.ensure_one()
        self.state = 'draft'
        return self.action_view_receipt()

    def action_view_receipt(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Receipt',
            'res_model': 'purchases.receipt',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_open_purchase_order(self):
        self.ensure_one()
        return self.purchase_order_id.action_view_purchase_order()

    def action_back_to_receipts(self):
        self.ensure_one()
        return {
            'name': 'Receipts',
            'type': 'ir.actions.act_window',
            'res_model': 'purchases.receipt',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'context': self.env.context,
        }


class receipt_line(models.Model):
    _name = 'purchases.receipt.line'
    _description = 'Purchase Receipt Line'
    _order = 'id'

    receipt_id = fields.Many2one(
        comodel_name='purchases.receipt', string='Receipt',
        ondelete='cascade', index=True, required=True)
    purchase_order_line_id = fields.Many2one(
        comodel_name='purchases.purchase_order_line', string='PO Line',
        ondelete='set null', index=True)
    product_id = fields.Many2one(
        comodel_name='sales.products', string='Product',
        ondelete='set null', index=True)
    description = fields.Char(string="Description", required=True)
    ordered_qty = fields.Float(
        string="Ordered Qty", digits=(16, 2), readonly=True)
    quantity = fields.Float(string="Received Qty", digits=(16, 2), default=0.0)
    product_unit = fields.Many2one(
        related='product_id.product_unit', string="UoM")

    @api.onchange('purchase_order_line_id')
    def _onchange_purchase_order_line_id(self):
        if self.purchase_order_line_id:
            self.product_id = self.purchase_order_line_id.product_id
            self.description = self.purchase_order_line_id.description or self.purchase_order_line_id.product_id.product_name
            self.ordered_qty = self.purchase_order_line_id.quantity
            self.quantity = self.purchase_order_line_id.qty_to_receive


class PurchaseApproveWizard(models.TransientModel):
    _name = 'purchases.approve.wizard'
    _description = 'Purchase Approve Wizard'

    purchase_order_id = fields.Many2one(
        'purchases.purchase_order', required=True)
    message = fields.Html(
        default=lambda self: _("<p>Are you sure you want to approve this purchase order?</p>"))

    def action_confirm(self):
        self.ensure_one()
        return self.purchase_order_id.action_approve_final()


class PurchaseRejectWizard(models.TransientModel):
    _name = 'purchases.reject.wizard'
    _description = 'Purchase Reject Wizard'

    purchase_order_id = fields.Many2one(
        'purchases.purchase_order', required=True)
    reason = fields.Text(string="Reason", required=True)

    def action_reject_confirm(self):
        self.ensure_one()
        return self.purchase_order_id.with_context(reject_reason=self.reason).action_reject_final()


class PurchaseReturnWizard(models.TransientModel):
    _name = 'purchases.return.wizard'
    _description = 'Purchase Return Wizard'

    purchase_order_id = fields.Many2one(
        'purchases.purchase_order', required=True)
    reason = fields.Text(string="Reason", required=True)

    def action_return_confirm(self):
        self.ensure_one()
        return self.purchase_order_id.with_context(return_reason=self.reason).action_return_final()


class PurchaseReviseWizard(models.TransientModel):
    _name = 'purchases.revise.wizard'
    _description = 'Purchase Revise Wizard'

    purchase_order_id = fields.Many2one(
        'purchases.purchase_order', required=True)
    message = fields.Text(string="Message", required=True)

    def action_revise_confirm(self):
        self.ensure_one()
        return self.purchase_order_id.with_context(revise_message=self.message).action_revise_final()
