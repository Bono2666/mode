# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging
_logger = logging.getLogger(__name__)


class asset_model(models.Model):
    _name = 'assets.model'
    _description = 'Asset Model Template'
    _inherit = ['navigation.mixin']
    _rec_name = 'name'
    _menu_code = 'asset_model'

    name = fields.Char(string='Model Name', required=True)
    method = fields.Selection([
        ('straight_line', 'Straight Line'),
        ('declining', 'Declining Balance'),
        ('declining_then_straight', 'Declining then Straight Line'),
    ], string='Depreciation Method', required=True, default='straight_line')
    method_number = fields.Integer(string='Number of Periods', default=60)
    method_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Period Length', required=True, default='monthly')
    method_progress_factor = fields.Float(
        string='Declining Factor', default=0.10,
        help='Used for Declining and Declining then Straight Line methods')
    prorata_computation_type = fields.Selection([
        ('none', 'None'),
        ('constant_periods', 'Constant Periods'),
        ('based_on_days_per_period', 'Based on Days Per Period'),
    ], string='Prorata Computations', default='none')
    account_asset_id = fields.Many2one(
        'accounting.account', string='Asset Account',
        domain=[('type_id.code', '=', 'fixed_asset')], ondelete='set null')
    account_depreciation_id = fields.Many2one(
        'accounting.account', string='Depreciation Account',
        domain=[('type_id.code', '=', 'fixed_asset')], ondelete='set null',
        help='Accumulated Depreciation account (contra-asset)')
    account_depreciation_expense_id = fields.Many2one(
        'accounting.account', string='Depreciation Expense Account',
        domain=[('type_id.code', '=', 'expense')], ondelete='set null')
    journal_id = fields.Many2one(
        'accounting.journal', string='Depreciation Journal',
        domain=[('type', '=', 'general')], ondelete='set null')
    is_edit = fields.Boolean(default=False)


class asset(models.Model):
    _name = 'assets.asset'
    _description = 'Fixed Asset'
    _inherit = ['navigation.mixin']
    _rec_name = 'name'
    _menu_code = 'asset_list'

    name = fields.Char(string='Asset Name', required=True)
    asset_number = fields.Char(string='Asset Number', readonly=True, copy=False)
    asset_model_id = fields.Many2one(
        'assets.model', string='Asset Model',
        ondelete='set null', index=True,
        help='Auto-fills depreciation method and accounts from template')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('close', 'Closed'),
        ('disposed', 'Disposed'),
    ], string='Status', default='draft', readonly=True, copy=False)
    acquisition_date = fields.Date(string='Acquisition Date')
    first_depreciation_date = fields.Date(string='First Depreciation Date')
    original_value = fields.Float(
        string='Original Value', required=True, digits=(16, 0), default=0.0)
    salvage_value = fields.Float(
        string='Salvage Value', digits=(16, 0), default=0.0)
    depreciable_value = fields.Float(
        string='Depreciable Value', compute='_compute_depreciable_value',
        store=True, digits=(16, 0))
    book_value = fields.Float(
        string='Book Value', compute='_compute_book_value',
        store=True, digits=(16, 0))
    fair_value = fields.Float(
        string='Fair Value', compute='_compute_fair_value',
        store=True, digits=(16, 0))
    last_revaluation_date = fields.Date(
        string='Last Revaluation Date', compute='_compute_last_revaluation',
        store=True)

    method = fields.Selection([
        ('straight_line', 'Straight Line'),
        ('declining', 'Declining Balance'),
        ('declining_then_straight', 'Declining then Straight Line'),
    ], string='Depreciation Method', default='straight_line')
    method_number = fields.Integer(string='Number of Periods', default=60)
    method_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Period Length', default='monthly')
    method_progress_factor = fields.Float(
        string='Declining Factor', default=0.10)
    prorata_computation_type = fields.Selection([
        ('none', 'None'),
        ('constant_periods', 'Constant Periods'),
        ('based_on_days_per_period', 'Based on Days Per Period'),
    ], string='Prorata Computations', default='none')

    account_asset_id = fields.Many2one(
        'accounting.account', string='Asset Account',
        domain=[('type_id.code', '=', 'fixed_asset')], ondelete='set null')
    account_depreciation_id = fields.Many2one(
        'accounting.account', string='Depreciation Account',
        domain=[('type_id.code', '=', 'fixed_asset')], ondelete='set null')
    account_depreciation_expense_id = fields.Many2one(
        'accounting.account', string='Depreciation Expense Account',
        domain=[('type_id.code', '=', 'expense')], ondelete='set null')
    journal_id = fields.Many2one(
        'accounting.journal', string='Depreciation Journal',
        domain=[('type', '=', 'general')], ondelete='set null')

    purchase_line_id = fields.Many2one(
        'purchases.bill.line', string='Purchase Bill Line',
        ondelete='set null', index=True, readonly=True)
    custodian_id = fields.Many2one(
        'general.custom_users', string='Custodian',
        ondelete='set null', index=True)
    location = fields.Char(string='Location')
    analytic_distribution = fields.Json(string='Analytic Distribution')

    account_revaluation_surplus_id = fields.Many2one(
        'accounting.account', string='Revaluation Surplus Account',
        domain=[('type_id.code', '=', 'equity')], ondelete='set null')
    account_revaluation_loss_id = fields.Many2one(
        'accounting.account', string='Impairment Loss Account',
        domain=[('type_id.code', '=', 'expense')], ondelete='set null')

    disposal_move_id = fields.Many2one(
        'accounting.move', string='Disposal Journal Entry',
        readonly=True, ondelete='set null')

    depreciation_line_ids = fields.One2many(
        'assets.depreciation_line', 'asset_id', string='Depreciation Lines')
    revaluation_line_ids = fields.One2many(
        'assets.revaluation_line', 'asset_id', string='Revaluation History')

    user_can_confirm = fields.Boolean(
        compute='_compute_user_can_confirm', string='Can Confirm')
    user_can_dispose = fields.Boolean(
        compute='_compute_user_can_dispose', string='Can Dispose')
    is_edit = fields.Boolean(default=False)

    # --- Computed fields ---

    @api.depends('original_value', 'salvage_value')
    def _compute_depreciable_value(self):
        for record in self:
            record.depreciable_value = record.original_value - record.salvage_value

    @api.depends('original_value', 'fair_value', 'depreciation_line_ids',
                 'depreciation_line_ids.depreciation_value',
                 'depreciation_line_ids.state',
                 'revaluation_line_ids.state',
                 'revaluation_line_ids.revaluation_date')
    def _compute_book_value(self):
        for record in self:
            if record.state in ('draft', 'disposed'):
                if record.state == 'disposed':
                    record.book_value = 0.0
                else:
                    record.book_value = record.original_value
                continue
            base = record.fair_value if record.fair_value else record.original_value
            last_reval = record.revaluation_line_ids.filtered(
                lambda r: r.state == 'posted').sorted('revaluation_date')
            if last_reval:
                reval_date = last_reval[-1].revaluation_date
                accumulated = sum(
                    record.depreciation_line_ids
                    .filtered(lambda l: l.state == 'posted'
                              and l.depreciation_date > reval_date)
                    .mapped('depreciation_value')
                )
            else:
                accumulated = sum(
                    record.depreciation_line_ids
                    .filtered(lambda l: l.state == 'posted')
                    .mapped('depreciation_value')
                )
            record.book_value = base - accumulated

    @api.depends('original_value', 'revaluation_line_ids',
                 'revaluation_line_ids.fair_value_after',
                 'revaluation_line_ids.state')
    def _compute_fair_value(self):
        for record in self:
            posted_revals = record.revaluation_line_ids.filtered(
                lambda r: r.state == 'posted').sorted('revaluation_date')
            if posted_revals:
                record.fair_value = posted_revals[-1].fair_value_after
            else:
                record.fair_value = record.original_value

    @api.depends('revaluation_line_ids.revaluation_date',
                 'revaluation_line_ids.state')
    def _compute_last_revaluation(self):
        for record in self:
            posted_revals = record.revaluation_line_ids.filtered(
                lambda r: r.state == 'posted').sorted('revaluation_date')
            record.last_revaluation_date = (
                posted_revals[-1].revaluation_date if posted_revals else False
            )

    @api.depends_context('uid')
    def _compute_user_can_confirm(self):
        is_admin = self.env.user.has_group('base.group_system')
        for record in self:
            if is_admin:
                record.user_can_confirm = True
                continue
            access = self.env['general.auth'].sudo().search([
                ('custom_user_id.user_id', '=', self.env.uid),
                ('menu_id.menu_id', '=', 'asset_list'),
                ('can_confirm', '=', True),
            ], limit=1)
            record.user_can_confirm = bool(access)

    @api.depends_context('uid')
    def _compute_user_can_dispose(self):
        is_admin = self.env.user.has_group('base.group_system')
        for record in self:
            if is_admin:
                record.user_can_dispose = True
                continue
            access = self.env['general.auth'].sudo().search([
                ('custom_user_id.user_id', '=', self.env.uid),
                ('menu_id.menu_id', '=', 'asset_list'),
                ('can_dispose', '=', True),
            ], limit=1)
            record.user_can_dispose = bool(access)

    # --- CRUD ---

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('asset_number'):
                vals['asset_number'] = self.env['ir.sequence'].next_by_code(
                    'assets.asset') or '/'
        return super(asset, self).create(vals_list)

    @api.onchange('asset_model_id')
    def _onchange_asset_model_id(self):
        if self.asset_model_id:
            m = self.asset_model_id
            self.method = m.method
            self.method_number = m.method_number
            self.method_period = m.method_period
            self.method_progress_factor = m.method_progress_factor
            self.prorata_computation_type = m.prorata_computation_type
            self.account_asset_id = m.account_asset_id
            self.account_depreciation_id = m.account_depreciation_id
            self.account_depreciation_expense_id = m.account_depreciation_expense_id
            self.journal_id = m.journal_id

    # --- State Machine ---

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft assets can be confirmed."))
            if not record.original_value or record.original_value <= 0:
                raise UserError(_("Original Value must be greater than zero."))
            if not record.account_asset_id:
                raise UserError(_("Asset Account is required."))
            if not record.account_depreciation_id:
                raise UserError(_("Depreciation Account is required."))
            if not record.account_depreciation_expense_id:
                raise UserError(_("Depreciation Expense Account is required."))
            if not record.journal_id:
                raise UserError(_("Depreciation Journal is required."))
            if not record.method_number or record.method_number <= 0:
                raise UserError(_("Number of Periods must be greater than zero."))
            record.state = 'running'

    def action_compute_depreciation(self):
        for record in self:
            if record.state not in ('running', 'paused'):
                raise UserError(_(
                    "Depreciation can only be computed for running or paused assets."))
            has_posted = record.depreciation_line_ids.filtered(
                lambda l: l.state == 'posted')
            if has_posted:
                existing_draft = record.depreciation_line_ids.filtered(
                    lambda l: l.state == 'draft')
                if existing_draft:
                    existing_draft.unlink()
            else:
                record.depreciation_line_ids.unlink()
            record._generate_depreciation_lines()
        return True

    def action_pause(self):
        for record in self:
            if record.state != 'running':
                raise UserError(_("Only running assets can be paused."))
            record.state = 'paused'

    def action_resume(self):
        for record in self:
            if record.state != 'paused':
                raise UserError(_("Only paused assets can be resumed."))
            record.state = 'running'

    def _validate_accounts(self):
        self.ensure_one()
        if not self.account_asset_id:
            raise ValidationError(_('Asset Account is required.'))
        if not self.account_depreciation_id:
            raise ValidationError(_('Depreciation Account is required.'))
        if not self.account_depreciation_expense_id:
            raise ValidationError(_('Depreciation Expense Account is required.'))
        if not self.journal_id:
            raise ValidationError(_('Depreciation Journal is required.'))

    # --- Depreciation Line Generation ---

    def _generate_depreciation_lines(self):
        self.ensure_one()
        self._validate_accounts()

        depreciable = self.depreciable_value
        if depreciable <= 0:
            return

        method = self.method
        number = self.method_number
        factor = self.method_progress_factor
        start_date = self.first_depreciation_date or self.acquisition_date
        if not start_date:
            raise UserError(_(
                "First Depreciation Date or Acquisition Date is required."))

        if method == 'straight_line':
            self._generate_straight_line(depreciable, number, start_date)
        elif method == 'declining':
            self._generate_declining(depreciable, number, factor, start_date)
        elif method == 'declining_then_straight':
            self._generate_declining_then_sl(
                depreciable, number, factor, start_date)

    def _generate_straight_line(self, depreciable, number, start_date):
        self.ensure_one()
        amount_per_period = depreciable / number
        current_date = start_date
        seq = 1
        remaining = depreciable

        for i in range(number):
            depr_value = round(amount_per_period, 0)
            if i == number - 1:
                depr_value = round(remaining, 0)
            remaining -= depr_value

            self.env['assets.depreciation_line'].create({
                'asset_id': self.id,
                'sequence': seq,
                'depreciation_date': current_date,
                'depreciation_value': depr_value,
                'state': 'draft',
            })
            seq += 1
            current_date = self._next_period_date(current_date)

    def _generate_declining(self, depreciable, number, factor, start_date):
        self.ensure_one()
        current_date = start_date
        seq = 1
        book_val = depreciable

        for i in range(number):
            depr_value = round(book_val * factor, 0)
            if i == number - 1:
                depr_value = round(book_val, 0)
            if depr_value <= 0:
                break
            book_val -= depr_value

            self.env['assets.depreciation_line'].create({
                'asset_id': self.id,
                'sequence': seq,
                'depreciation_date': current_date,
                'depreciation_value': depr_value,
                'state': 'draft',
            })
            seq += 1
            current_date = self._next_period_date(current_date)

    def _generate_declining_then_sl(self, depreciable, number, factor,
                                    start_date):
        self.ensure_one()
        current_date = start_date
        seq = 1
        book_val = depreciable

        for i in range(number):
            remaining_periods = number - i
            db_value = round(book_val * factor, 0)
            sl_value = round(book_val / remaining_periods if remaining_periods > 0 else 0, 0)
            depr_value = max(db_value, sl_value)
            if i == number - 1:
                depr_value = round(book_val, 0)
            if depr_value <= 0:
                break
            book_val -= depr_value

            self.env['assets.depreciation_line'].create({
                'asset_id': self.id,
                'sequence': seq,
                'depreciation_date': current_date,
                'depreciation_value': depr_value,
                'state': 'draft',
            })
            seq += 1
            current_date = self._next_period_date(current_date)

    def _next_period_date(self, current_date):
        if self.method_period == 'monthly':
            month = current_date.month + 1
            year = current_date.year
            if month > 12:
                month = 1
                year += 1
            day = min(current_date.day,
                       self._days_in_month(year, month))
            return date(year, month, day)
        else:
            return date(current_date.year + 1, current_date.month,
                        current_date.day)

    @staticmethod
    def _days_in_month(year, month):
        if month == 12:
            return 31
        return (date(year, month + 1, 1) - date(year, month, 1)).days

    # --- Smart Buttons ---

    def action_view_depreciation_lines(self):
        self.ensure_one()
        return {
            'name': _('Depreciation Board'),
            'type': 'ir.actions.act_window',
            'res_model': 'assets.depreciation_line',
            'view_mode': 'tree,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
            'target': 'current',
        }

    def action_view_revaluation_history(self):
        self.ensure_one()
        return {
            'name': _('Revaluation History'),
            'type': 'ir.actions.act_window',
            'res_model': 'assets.revaluation_line',
            'view_mode': 'tree,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
            'target': 'current',
        }

    def action_view_disposal_move(self):
        self.ensure_one()
        if not self.disposal_move_id:
            raise UserError(_("No disposal journal entry found."))
        return {
            'name': _('Disposal Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.move',
            'view_mode': 'form',
            'res_id': self.disposal_move_id.id,
            'target': 'current',
        }

    def action_open_disposal_wizard(self):
        self.ensure_one()
        if self.state != 'running':
            raise UserError(_("Only running assets can be disposed."))
        return {
            'name': _('Dispose Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'assets.disposal_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_book_value': self.book_value,
            },
        }

    def action_open_revaluation_wizard(self):
        self.ensure_one()
        if self.state != 'running':
            raise UserError(_("Only running assets can be revalued."))
        remaining_posted = self.depreciation_line_ids.filtered(
            lambda l: l.state == 'posted')
        total_periods = self.method_number or 0
        used_periods = len(remaining_posted)
        remaining_life = max(total_periods - used_periods, 0)
        return {
            'name': _('Revalue Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'assets.revaluation_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_book_value_current': self.book_value,
                'default_remaining_useful_life': remaining_life,
            },
        }


class depreciation_line(models.Model):
    _name = 'assets.depreciation_line'
    _description = 'Depreciation Line'
    _order = 'sequence, id'

    asset_id = fields.Many2one(
        'assets.asset', string='Asset', ondelete='cascade', index=True,
        required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    depreciation_date = fields.Date(string='Depreciation Date', required=True)
    depreciation_value = fields.Float(
        string='Depreciation Amount', required=True, digits=(16, 0))
    accumulated_value = fields.Float(
        string='Accumulated Depreciation', compute='_compute_accumulated',
        store=True, digits=(16, 0))
    remaining_value = fields.Float(
        string='Remaining Value', compute='_compute_remaining',
        store=True, digits=(16, 0))
    move_id = fields.Many2one(
        'accounting.move', string='Journal Entry',
        readonly=True, ondelete='set null', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='Status', default='draft', readonly=True, copy=False)

    @api.depends('asset_id', 'depreciation_value', 'state',
                 'sequence')
    def _compute_accumulated(self):
        for line in self:
            if not line.asset_id:
                line.accumulated_value = 0.0
                continue
            previous = self.env['assets.depreciation_line'].search([
                ('asset_id', '=', line.asset_id.id),
                ('sequence', '<', line.sequence),
                ('state', '=', 'posted'),
            ])
            line.accumulated_value = (
                sum(previous.mapped('depreciation_value'))
                + (line.depreciation_value if line.state == 'posted' else 0.0)
            )

    @api.depends('asset_id', 'accumulated_value')
    def _compute_remaining(self):
        for line in self:
            base = line.asset_id.fair_value if line.asset_id.fair_value else (
                line.asset_id.original_value)
            line.remaining_value = base - line.accumulated_value

    def action_post_depreciation(self):
        for line in self:
            if line.state == 'posted':
                continue
            if not line.asset_id:
                continue
            asset = line.asset_id
            asset._validate_accounts()

            journal = asset.journal_id
            expense_account = asset.account_depreciation_expense_id
            depreciation_account = asset.account_depreciation_id

            move = self.env['accounting.move'].create({
                'ref': 'Depreciation: %s - %s' % (
                    asset.asset_number or asset.name, line.depreciation_date),
                'date': line.depreciation_date,
                'journal_id': journal.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': expense_account.id,
                        'name': 'Depreciation Expense',
                        'debit': line.depreciation_value,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': depreciation_account.id,
                        'name': 'Accumulated Depreciation',
                        'debit': 0.0,
                        'credit': line.depreciation_value,
                    }),
                ],
            })
            if move.is_balanced:
                try:
                    move.action_post()
                except UserError:
                    pass
            line.move_id = move.id
            line.state = 'posted'

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No journal entry linked."))
        return {
            'name': _('Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
            'target': 'current',
        }


class revaluation_line(models.Model):
    _name = 'assets.revaluation_line'
    _description = 'Asset Revaluation Line'
    _order = 'revaluation_date, id'

    asset_id = fields.Many2one(
        'assets.asset', string='Asset', ondelete='cascade', index=True,
        required=True)
    revaluation_date = fields.Date(
        string='Revaluation Date', required=True, default=fields.Date.today)
    book_value_before = fields.Float(
        string='Book Value Before', required=True, digits=(16, 0))
    fair_value_after = fields.Float(
        string='Fair Value After', required=True, digits=(16, 0))
    surplus_deficit_value = fields.Float(
        string='Surplus / Deficit', compute='_compute_surplus_deficit',
        store=True, digits=(16, 0))
    remaining_useful_life = fields.Integer(
        string='Remaining Useful Life (periods)',
        help='Remaining periods for depreciation after this revaluation')
    note = fields.Text(string='Justification / Notes')
    move_id = fields.Many2one(
        'accounting.move', string='Journal Entry',
        readonly=True, ondelete='set null', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='Status', default='draft', readonly=True, copy=False)

    @api.depends('fair_value_after', 'book_value_before')
    def _compute_surplus_deficit(self):
        for line in self:
            line.surplus_deficit_value = line.fair_value_after - line.book_value_before

    def action_post_revaluation(self):
        for line in self:
            if line.state == 'posted':
                continue
            if not line.asset_id:
                continue
            asset = line.asset_id
            value_diff = line.surplus_deficit_value

            if value_diff == 0:
                continue

            asset._validate_accounts()

            journal = asset.journal_id
            asset_account = asset.account_asset_id

            lines_vals = []
            if value_diff > 0:
                surplus_account = asset.account_revaluation_surplus_id
                if not surplus_account:
                    raise UserError(_(
                        "Revaluation Surplus Account is required on asset."))
                lines_vals = [
                    (0, 0, {
                        'account_id': asset_account.id,
                        'name': 'Revaluation Surplus',
                        'debit': value_diff,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': surplus_account.id,
                        'name': 'Revaluation Surplus',
                        'debit': 0.0,
                        'credit': value_diff,
                    }),
                ]
            else:
                deficit_abs = abs(value_diff)
                surplus_account = asset.account_revaluation_surplus_id
                impairment_account = asset.account_revaluation_loss_id
                if not impairment_account:
                    raise UserError(_(
                        "Impairment Loss Account is required on asset."))

                accumulated_surplus = sum(
                    asset.revaluation_line_ids
                    .filtered(lambda r: r.state == 'posted'
                              and r.surplus_deficit_value > 0)
                    .mapped('surplus_deficit_value')
                )

                surplus_reduction = min(deficit_abs, accumulated_surplus)
                impairment_amount = deficit_abs - surplus_reduction

                if surplus_account and surplus_reduction > 0:
                    lines_vals.append((0, 0, {
                        'account_id': surplus_account.id,
                        'name': 'Deficit - Reduce Surplus',
                        'debit': surplus_reduction,
                        'credit': 0.0,
                    }))
                if impairment_amount > 0:
                    lines_vals.append((0, 0, {
                        'account_id': impairment_account.id,
                        'name': 'Impairment Loss',
                        'debit': impairment_amount,
                        'credit': 0.0,
                    }))
                lines_vals.append((0, 0, {
                    'account_id': asset_account.id,
                    'name': 'Revaluation Deficit',
                    'debit': 0.0,
                    'credit': deficit_abs,
                }))

            move = self.env['accounting.move'].create({
                'ref': 'Revaluation: %s - %s' % (
                    asset.asset_number or asset.name,
                    line.revaluation_date),
                'date': line.revaluation_date,
                'journal_id': journal.id,
                'line_ids': lines_vals,
            })
            if move.is_balanced:
                try:
                    move.action_post()
                except UserError:
                    pass
            line.move_id = move.id
            line.state = 'posted'

            asset.action_compute_depreciation()

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No journal entry linked."))
        return {
            'name': _('Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
            'target': 'current',
        }
