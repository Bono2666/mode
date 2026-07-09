# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)
from datetime import timedelta


# =============================================================================
# GROUP A: CORE CONFIGURATION MODELS
# =============================================================================

class accounting_account_type(models.Model):
    _name = 'accounting.account.type'
    _description = 'Account Type'
    _inherit = ['navigation.mixin']
    _order = 'sequence, id'
    _menu_code = 'account_types'

    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    is_edit = fields.Boolean(string='Is Edit', default=False)


class accounting_account(models.Model):
    _name = 'accounting.account'
    _description = 'Chart of Accounts'
    _inherit = ['navigation.mixin']
    _rec_name = 'code'
    _order = 'code, id'
    _menu_code = 'chart_of_accounts'

    code = fields.Char(string='Account Code', required=True)
    name = fields.Char(string='Account Name', required=True)
    type_id = fields.Many2one(
        comodel_name='accounting.account.type', string='Account Type',
        ondelete='restrict', index=True, required=True)
    reconcile = fields.Boolean(
        string='Reconcile', default=False,
        help="Allow reconciliation of this account (AR/AP)")
    currency_id = fields.Many2one(
        comodel_name='res.currency', string='Currency',
        default=lambda self: self.env['res.currency'].search(
            [('name', '=', 'IDR')], limit=1)
        or self.env.company.currency_id)
    active = fields.Boolean(string='Active', default=True)
    parent_id = fields.Many2one(
        comodel_name='accounting.account', string='Parent Account',
        ondelete='set null', index=True)
    child_ids = fields.One2many(
        comodel_name='accounting.account', inverse_name='parent_id',
        string='Child Accounts')
    is_edit = fields.Boolean(string='Is Edit', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'accounting.account') or '/'
        return super(accounting_account, self).create(vals_list)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Search accounts by both code and name."""
        if not args:
            args = []
        if name:
            domain = ['|', ('code', operator, name),
                      ('name', operator, name)]
            accounts = self.search(domain + args, limit=limit)
            return accounts.name_get()
        return super(accounting_account, self).name_search(
            name=name, args=args, operator=operator, limit=limit)

    def name_get(self):
        result = []
        for record in self:
            name = '[%s] %s' % (record.code, record.name)
            result.append((record.id, name))
        return result


class accounting_journal(models.Model):
    _name = 'accounting.journal'
    _description = 'Accounting Journal'
    _inherit = ['navigation.mixin']
    _order = 'code, id'
    _menu_code = 'accounting_journals'

    name = fields.Char(string='Journal Name', required=True)
    code = fields.Char(string='Journal Code', required=True)
    type = fields.Selection([
        ('sale', 'Sales'),
        ('purchase', 'Purchase'),
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('general', 'General'),
    ], string='Journal Type', required=True, default='general')
    default_debit_account_id = fields.Many2one(
        comodel_name='accounting.account', string='Default Debit Account',
        ondelete='set null', index=True)
    default_credit_account_id = fields.Many2one(
        comodel_name='accounting.account', string='Default Credit Account',
        ondelete='set null', index=True)
    active = fields.Boolean(string='Active', default=True)
    is_edit = fields.Boolean(string='Is Edit', default=False)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Journal code must be unique!'),
    ]


class accounting_fiscal_year(models.Model):
    _name = 'accounting.fiscal.year'
    _description = 'Fiscal Year'
    _inherit = ['navigation.mixin']
    _order = 'date_from desc, id'
    _menu_code = 'fiscal_years'

    name = fields.Char(string='Name', required=True)
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='Status', default='open', required=True)
    period_ids = fields.One2many(
        comodel_name='accounting.period', inverse_name='fiscal_year_id',
        string='Periods')
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company',
        default=lambda self: self.env.company)
    is_edit = fields.Boolean(string='Is Edit', default=False)

    def action_close_year(self):
        self.ensure_one()
        self.state = 'closed'
        self.period_ids.write({'state': 'closed'})

    def action_open_year(self):
        self.ensure_one()
        self.state = 'open'


class accounting_period(models.Model):
    _name = 'accounting.period'
    _description = 'Accounting Period'
    _inherit = ['navigation.mixin']
    _order = 'date_from asc, id'
    _menu_code = 'periods'

    name = fields.Char(string='Name', required=True)
    fiscal_year_id = fields.Many2one(
        comodel_name='accounting.fiscal.year', string='Fiscal Year',
        ondelete='cascade', index=True, required=True)
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='Status', default='open', required=True)
    is_edit = fields.Boolean(string='Is Edit', default=False)

    def action_close_period(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('This period is already closed.'))
        self.state = 'closed'

    def action_open_period(self):
        self.ensure_one()
        if self.fiscal_year_id.state == 'closed':
            raise UserError(_(
                'Cannot open a period in a closed fiscal year.'))
        self.state = 'open'

    @api.model
    def get_current_period(self):
        """Return the accounting period that contains today's date."""
        today = fields.Date.today()
        period = self.search([
            ('date_from', '<=', today),
            ('date_to', '>=', today),
            ('state', '=', 'open'),
        ], limit=1)
        return period


# =============================================================================
# GROUP B: TRANSACTION MODELS
# =============================================================================

class accounting_move(models.Model):
    _name = 'accounting.move'
    _description = 'Journal Entry'
    _inherit = ['navigation.mixin']
    _rec_name = 'name'
    _order = 'date desc, id desc'
    _menu_code = 'accounting_moves'

    name = fields.Char(string='Entry Number', readonly=True, copy=False)
    ref = fields.Char(string='Reference')
    date = fields.Date(
        string='Date', default=fields.Date.today, required=True)
    journal_id = fields.Many2one(
        comodel_name='accounting.journal', string='Journal',
        ondelete='restrict', index=True, required=True)
    currency_id = fields.Many2one(
        comodel_name='res.currency', string='Currency',
        default=lambda self: self.env['res.currency'].search(
            [('name', '=', 'IDR')], limit=1)
        or self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', required=True)
    posted_date = fields.Datetime(string='Posted On', readonly=True, copy=False)
    line_ids = fields.One2many(
        comodel_name='accounting.move.line', inverse_name='move_id',
        string='Journal Items')
    total_debit = fields.Float(
        string='Total Debit', compute='_compute_totals', store=True,
        digits=(16, 0))
    total_credit = fields.Float(
        string='Total Credit', compute='_compute_totals', store=True,
        digits=(16, 0))
    is_balanced = fields.Boolean(
        string='Balanced', compute='_compute_totals', store=True)
    is_edit = fields.Boolean(string='Is Edit', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'accounting.move') or '/'
        return super(accounting_move, self).create(vals_list)

    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_totals(self):
        for record in self:
            record.total_debit = sum(record.line_ids.mapped('debit'))
            record.total_credit = sum(record.line_ids.mapped('credit'))
            record.is_balanced = (
                abs(record.total_debit - record.total_credit) < 0.01
            )

    def action_post(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_(
                    'Only draft journal entries can be posted.'
                ))
            if not record.is_balanced:
                raise UserError(_(
                    'The journal entry is not balanced.\n'
                    'Total Debit: %(debit)s\n'
                    'Total Credit: %(credit)s\n'
                    'Difference: %(diff)s',
                    debit=record.total_debit,
                    credit=record.total_credit,
                    diff=abs(record.total_debit - record.total_credit),
                ))
            if not record.line_ids:
                raise UserError(_(
                    'Please add journal items before posting.'
                ))
            # Validate: check that the move date is within an open period
            period = self.env['accounting.period'].search([
                ('date_from', '<=', record.date),
                ('date_to', '>=', record.date),
                ('state', '=', 'open'),
            ], limit=1)
            if not period:
                raise UserError(_(
                    'No open accounting period found for the date %(date)s.',
                    date=record.date,
                ))
            record.state = 'posted'
            record.posted_date = fields.Datetime.now()

    def action_cancel(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'cancel'
            elif record.state == 'posted':
                record.state = 'cancel'
            else:
                raise UserError(_(
                    'Cannot cancel a journal entry that is already cancelled.'
                ))

    def action_reset_to_draft(self):
        for record in self:
            if record.state != 'cancel':
                raise UserError(_(
                    'Only cancelled journal entries can be reset to draft.'
                ))
            record.state = 'draft'
            record.posted_date = False

    def unlink(self):
        for record in self:
            if record.state == 'posted':
                raise UserError(_(
                    'Cannot delete a posted journal entry. Cancel it first.'
                ))
        return super(accounting_move, self).unlink()


class accounting_move_line(models.Model):
    _name = 'accounting.move.line'
    _description = 'Journal Entry Line'
    _rec_name = 'name'
    _order = 'sequence, id'

    move_id = fields.Many2one(
        comodel_name='accounting.move', string='Journal Entry',
        ondelete='cascade', index=True, required=True)
    currency_id = fields.Many2one(
        comodel_name='res.currency', related='move_id.currency_id',
        string='Currency', store=True)
    sequence = fields.Integer(string='Sequence', default=10)
    account_id = fields.Many2one(
        comodel_name='accounting.account', string='Account',
        ondelete='restrict', index=True, required=True)
    account_name = fields.Char(
        string='Account Name', related='account_id.name',
        store=True, readonly=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Partner',
        ondelete='set null', index=True)
    name = fields.Char(string='Label')
    debit = fields.Float(string='Debit', default=0.0, digits=(16, 0))
    credit = fields.Float(string='Credit', default=0.0, digits=(16, 0))
    date_maturity = fields.Date(string='Due Date')
    reconciled = fields.Boolean(string='Reconciled', default=False,
                                copy=False)

    @api.constrains('debit', 'credit')
    def _check_debit_credit(self):
        for line in self:
            if line.debit < 0 or line.credit < 0:
                raise UserError(_(
                    'Debit and credit amounts cannot be negative.'
                ))
            if line.debit > 0 and line.credit > 0:
                raise UserError(_(
                    'A journal item cannot have both debit and credit.'
                ))

    @api.onchange('account_id')
    def _onchange_account_id(self):
        if self.account_id:
            if not self.name:
                self.name = self.account_id.name


# =============================================================================
# GROUP C: BANK STATEMENT MODELS
# =============================================================================

class accounting_bank_statement(models.Model):
    _name = 'accounting.bank.statement'
    _description = 'Bank Statement'
    _inherit = ['navigation.mixin']
    _rec_name = 'name'
    _order = 'date desc, id desc'
    _menu_code = 'bank_statements'

    name = fields.Char(string='Statement Number', readonly=True, copy=False)
    journal_id = fields.Many2one(
        comodel_name='accounting.journal', string='Journal',
        ondelete='restrict', index=True, required=True,
        domain=[('type', 'in', ['bank', 'cash'])])
    currency_id = fields.Many2one(
        comodel_name='res.currency', string='Currency',
        default=lambda self: self.env['res.currency'].search(
            [('name', '=', 'IDR')], limit=1)
        or self.env.company.currency_id)
    date = fields.Date(
        string='Date', default=fields.Date.today, required=True)
    balance_start = fields.Float(
        string='Opening Balance', digits=(16, 0), default=0.0)
    balance_end = fields.Float(
        string='Closing Balance', digits=(16, 0), default=0.0,
        compute='_compute_balance_end', store=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='Status', default='open', required=True)
    line_ids = fields.One2many(
        comodel_name='accounting.bank.statement.line',
        inverse_name='statement_id', string='Statement Lines')
    is_edit = fields.Boolean(string='Is Edit', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'accounting.bank.statement') or '/'
        return super(accounting_bank_statement, self).create(vals_list)

    @api.depends('balance_start', 'line_ids.amount')
    def _compute_balance_end(self):
        for record in self:
            total_lines = sum(record.line_ids.mapped('amount'))
            record.balance_end = record.balance_start + total_lines

    def action_close_statement(self):
        self.ensure_one()
        self.state = 'closed'

    def action_open_statement(self):
        self.ensure_one()
        self.state = 'open'


class accounting_bank_statement_line(models.Model):
    _name = 'accounting.bank.statement.line'
    _description = 'Bank Statement Line'
    _order = 'date, id'

    statement_id = fields.Many2one(
        comodel_name='accounting.bank.statement', string='Statement',
        ondelete='cascade', index=True, required=True)
    currency_id = fields.Many2one(
        comodel_name='res.currency', related='statement_id.currency_id',
        string='Currency', store=True)
    date = fields.Date(string='Date', default=fields.Date.today)
    ref = fields.Char(string='Reference')
    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Partner',
        ondelete='set null', index=True)
    amount = fields.Float(string='Amount', digits=(16, 0), default=0.0)
    move_line_ids = fields.Many2many(
        comodel_name='accounting.move.line', string='Matched Journal Items',
        domain=[('reconciled', '=', False)])
    state = fields.Selection([
        ('unmatched', 'Unmatched'),
        ('matched', 'Matched'),
        ('reconciled', 'Reconciled'),
    ], string='Status', default='unmatched')


# =============================================================================
# GROUP D: INHERITED EXTENSIONS (sales + purchases integration)
# =============================================================================

class accounting_tax(models.Model):
    _inherit = 'sales.taxes'

    tax_account_id = fields.Many2one(
        comodel_name='accounting.account', string='Tax Account',
        ondelete='set null', index=True,
        domain=[('type_id.code', '=', 'tax')])
    tax_group = fields.Selection([
        ('sales', 'Sales Tax'),
        ('purchases', 'Purchase Tax'),
    ], string='Tax Group', default='sales')


class sales_invoice_accounting(models.Model):
    _inherit = 'sales.invoice'

    accounting_move_id = fields.Many2one(
        comodel_name='accounting.move', string='Accounting Entry',
        readonly=True, copy=False, ondelete='set null', index=True)
    accounting_move_count = fields.Integer(
        string='Journal Entry Count', compute='_compute_accounting_move_count')

    def _compute_accounting_move_count(self):
        for record in self:
            record.accounting_move_count = 1 if record.accounting_move_id else 0

    def _get_receivable_account(self):
        """Return the AR account. Default: account code 110000."""
        account = self.env['accounting.account'].search(
            [('code', '=', '110000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'receivable')], limit=1)
        if not account:
            raise UserError(_(
                'No Receivable account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_revenue_account(self):
        """Return the Revenue account. Default: account code 400000."""
        account = self.env['accounting.account'].search(
            [('code', '=', '400000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'income')], limit=1)
        if not account:
            raise UserError(_(
                'No Revenue account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_tax_account(self, tax_id):
        """Return the tax account for a given tax."""
        if tax_id and tax_id.tax_account_id:
            return tax_id.tax_account_id
        account = self.env['accounting.account'].search(
            [('code', '=', '210000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'tax')], limit=1)
        return account

    def _get_sales_journal(self):
        """Return the Sales journal."""
        journal = self.env['accounting.journal'].search(
            [('type', '=', 'sale')], limit=1)
        if not journal:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_(
                'No journal found. Please configure Sales or General journal.'
            ))
        return journal

    def action_post(self):
        """Override: post original invoice, then create accounting move."""
        result = super(sales_invoice_accounting, self).action_post()
        self._create_accounting_move()
        return result

    def action_set_to_draft(self):
        """Override: cancel linked accounting move before resetting."""
        for record in self:
            if record.accounting_move_id:
                if record.accounting_move_id.state == 'posted':
                    record.accounting_move_id.action_cancel()
        return super(sales_invoice_accounting, self).action_set_to_draft()

    def _create_accounting_move(self):
        """Create accounting journal entries for this invoice."""
        self.ensure_one()
        # Skip credit notes for now — handled via sign reversal
        if self.document_type == 'credit_note':
            return self._create_credit_note_accounting_move()

        journal = self._get_sales_journal()
        receivable_account = self._get_receivable_account()
        revenue_account = self._get_revenue_account()
        sign = -1 if self.document_type == 'credit_note' else 1

        lines = []
        seq = 1

        # --- 1. Receivable line(s) — split by payment term installments ---
        if (self.payment_terms_id and
                self.payment_terms_id.payment_terms_ids and
                self.amount_total):
            term_lines = self.payment_terms_id.payment_terms_ids.sorted(
                key=lambda l: l.no_of_days)
            remaining = self.amount_total
            total_terms = len(term_lines)
            cum_pct = 0.0
            for idx, tline in enumerate(term_lines, start=1):
                if idx == total_terms:
                    amount = remaining
                else:
                    pct = tline.percentage / 100.0
                    amount = round(self.amount_total * pct, 0)
                remaining -= amount
                due_date = (
                    self.invoice_date + timedelta(days=tline.no_of_days)
                    if self.invoice_date else fields.Date.today()
                )
                lines.append((0, 0, {
                    'sequence': seq,
                    'account_id': receivable_account.id,
                    'partner_id': (
                        self.customer_id.partner_id.id
                        if self.customer_id and self.customer_id.partner_id
                        else False
                    ),
                    'name': '%s - Installment %s/%s' % (
                        self.invoice_number, idx, total_terms),
                    'debit': amount if sign > 0 else 0.0,
                    'credit': 0.0 if sign > 0 else amount,
                    'date_maturity': due_date,
                }))
                seq += 1
        else:
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': receivable_account.id,
                'partner_id': (
                    self.customer_id.partner_id.id
                    if self.customer_id and self.customer_id.partner_id
                    else False
                ),
                'name': self.invoice_number,
                'debit': self.amount_total if sign > 0 else 0.0,
                'credit': 0.0 if sign > 0 else self.amount_total,
                'date_maturity': self.invoice_date or fields.Date.today(),
            }))
            seq += 1

        # --- 2. Revenue line(s) — credit each line's subtotal ---
        for line in self.line_ids.sorted('sequence'):
            if not line.sub_total:
                continue
            # Resolve per-line account: product category > default revenue account
            line_account = revenue_account
            if line.product_id and line.product_id.product_category:
                cat = line.product_id.product_category
                if cat.income_account_id:
                    line_account = cat.income_account_id
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': line_account.id,
                'partner_id': (
                    self.customer_id.partner_id.id
                    if self.customer_id and self.customer_id.partner_id
                    else False
                ),
                'name': line.description or 'Invoice Line',
                'debit': abs(line.sub_total) if sign < 0 else 0.0,
                'credit': abs(line.sub_total) if sign > 0 else 0.0,
            }))
            seq += 1

        # --- 3. Tax line(s) — grouped by tax ---
        grouped_taxes = {}
        for line in self.line_ids:
            if not line.tax_amount:
                continue
            tax = line.tax_id
            tax_key = tax.id if tax else 0
            if tax_key not in grouped_taxes:
                tax_account = self._get_tax_account(tax)
                grouped_taxes[tax_key] = {
                    'name': tax.name if tax else 'Tax',
                    'amount': 0.0,
                    'account_id': tax_account.id if tax_account else False,
                }
            grouped_taxes[tax_key]['amount'] += line.tax_amount

        for tax_data in grouped_taxes.values():
            if not tax_data['amount'] or not tax_data['account_id']:
                continue
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': tax_data['account_id'],
                'partner_id': (
                    self.customer_id.partner_id.id
                    if self.customer_id and self.customer_id.partner_id
                    else False
                ),
                'name': tax_data['name'],
                'debit': tax_data['amount'] if sign < 0 else 0.0,
                'credit': tax_data['amount'] if sign > 0 else 0.0,
            }))
            seq += 1

        # --- 3b. Commission lines ---
        if self.sales_name:
            plans = self.env['accounting.commission.plan'].sudo().search([
                ('active', '=', True),
            ], limit=1)
            if plans:
                plan = plans
                base_amount = self.amount_untaxed if plan.based_on == 'untaxed' else self.amount_total
                rate = plan.rate
                commission_amount = (base_amount * rate / 100.0) if plan.type == 'percentage' else rate

                if commission_amount > 0:
                    expense_account = plan.expense_account_id
                    if not expense_account:
                        expense_account = self.env['accounting.account'].sudo().search(
                            [('code', '=', '510000')], limit=1)
                    if not expense_account:
                        expense_account = self.env['accounting.account'].sudo().search(
                            [('type_id.code', '=', 'expense')], limit=1)

                    payable_account = plan.payable_account_id
                    if not payable_account:
                        payable_account = self.env['accounting.account'].sudo().search(
                            [('code', '=', '220000')], limit=1)
                    if not payable_account:
                        payable_account = self.env['accounting.account'].sudo().search(
                            [('type_id.code', '=', 'payable')], limit=1)
                    if not payable_account:
                        payable_account = self.env['accounting.account'].sudo().search(
                            [('type_id.code', '=', 'liability')], limit=1)

                    if expense_account:
                        lines.append((0, 0, {
                            'sequence': seq,
                            'account_id': expense_account.id,
                            'name': 'Commission: %s (%s%%)' % (self.sales_name.name, rate),
                            'debit': commission_amount,
                            'credit': 0.0,
                        }))
                        seq += 1

                    if payable_account:
                        lines.append((0, 0, {
                            'sequence': seq,
                            'account_id': payable_account.id,
                            'name': 'Commission Payable: %s' % self.sales_name.name,
                            'debit': 0.0,
                            'credit': commission_amount,
                            'partner_id': self.sales_name.user_id.partner_id.id if self.sales_name.user_id and self.sales_name.user_id.partner_id else False,
                        }))
                        seq += 1

                    # Auto-create and post settlement
                    settlement = self.env['accounting.commission.settlement'].sudo().create({
                        'invoice_id': self.id,
                        'salesperson_id': self.sales_name.id,
                        'plan_id': plan.id,
                        'date': fields.Date.today(),
                        'base_amount': base_amount,
                        'rate': rate,
                        'commission_amount': commission_amount,
                    })

        # --- 4. Create the accounting move ---
        if not lines:
            return

        move = self.env['accounting.move'].create({
            'ref': '%s: %s' % (self.invoice_number,
                               self.customer_id.customer_name if self.customer_id else ''),
            'date': self.invoice_date or fields.Date.today(),
            'journal_id': journal.id,
            'state': 'draft',
            'line_ids': lines,
        })
        # Auto-post if balanced
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass
        # Link commission settlement to this move and auto-post
        self.env['accounting.commission.settlement'].sudo().search([
            ('invoice_id', '=', self.id),
            ('state', '=', 'draft'),
        ]).write({
            'move_id': move.id,
            'state': 'posted',
        })

        self.accounting_move_id = move.id
        return move

    def _create_credit_note_accounting_move(self):
        """Create reversing accounting entries for a credit note."""
        self.ensure_one()
        journal = self._get_sales_journal()
        receivable_account = self._get_receivable_account()
        revenue_account = self._get_revenue_account()

        lines = []
        seq = 1

        # Credit note: reverse the invoice — credit AR, debit Revenue
        # Receivable (credit)
        lines.append((0, 0, {
            'sequence': seq,
            'account_id': receivable_account.id,
            'partner_id': (
                self.customer_id.partner_id.id
                if self.customer_id and self.customer_id.partner_id
                else False
            ),
            'name': 'Credit Note: %s' % self.invoice_number,
            'debit': 0.0,
            'credit': abs(self.amount_total),
            'date_maturity': self.invoice_date or fields.Date.today(),
        }))
        seq += 1

        # Revenue lines (debit — reversing)
        for line in self.line_ids.sorted('sequence'):
            if not line.sub_total:
                continue
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': revenue_account.id,
                'partner_id': (
                    self.customer_id.partner_id.id
                    if self.customer_id and self.customer_id.partner_id
                    else False
                ),
                'name': 'Credit Note: %s' % (line.description or ''),
                'debit': abs(line.sub_total),
                'credit': 0.0,
            }))
            seq += 1

        # Tax lines (debit — reversing)
        grouped_taxes = {}
        for line in self.line_ids:
            if not line.tax_amount:
                continue
            tax = line.tax_id
            tax_key = tax.id if tax else 0
            if tax_key not in grouped_taxes:
                tax_account = self._get_tax_account(tax)
                grouped_taxes[tax_key] = {
                    'name': tax.name if tax else 'Tax',
                    'amount': 0.0,
                    'account_id': tax_account.id if tax_account else False,
                }
            grouped_taxes[tax_key]['amount'] += line.tax_amount

        for tax_data in grouped_taxes.values():
            if not tax_data['amount'] or not tax_data['account_id']:
                continue
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': tax_data['account_id'],
                'partner_id': (
                    self.customer_id.partner_id.id
                    if self.customer_id and self.customer_id.partner_id
                    else False
                ),
                'name': 'Credit Note: %s' % tax_data['name'],
                'debit': tax_data['amount'],
                'credit': 0.0,
            }))
            seq += 1

        if not lines:
            return

        move = self.env['accounting.move'].create({
            'ref': 'Credit Note: %s' % self.invoice_number,
            'date': self.invoice_date or fields.Date.today(),
            'journal_id': journal.id,
            'state': 'draft',
            'line_ids': lines,
        })
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass
        # Link commission settlement to this move and auto-post
        self.env['accounting.commission.settlement'].sudo().search([
            ('invoice_id', '=', self.id),
            ('state', '=', 'draft'),
        ]).write({
            'move_id': move.id,
            'state': 'posted',
        })

        self.accounting_move_id = move.id
        return move

    def _get_extra_move_lines(self):
        """Hook for subclasses to inject additional journal lines (e.g. commission)."""
        return []

    def action_view_accounting_move(self):
        self.ensure_one()
        if not self.accounting_move_id:
            return
        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', 'accounting.move'),
            ('type', '=', 'form'),
        ], limit=1).id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'accounting.move',
            'view_mode': 'form',
            'res_id': self.accounting_move_id.id,
            'views': [(view_id, 'form')],
            'target': 'current',
        }


class sales_payment_accounting(models.Model):
    _inherit = 'sales.payment'

    accounting_move_id = fields.Many2one(
        comodel_name='accounting.move', string='Accounting Entry',
        readonly=True, copy=False, ondelete='set null', index=True)

    def _get_cash_bank_account(self):
        """Return the cash/bank account based on payment method."""
        account = self.env['accounting.account'].search(
            [('code', '=', '100000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', 'in', ['bank', 'cash'])], limit=1)
        if not account:
            raise UserError(_(
                'No Cash/Bank account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_receivable_account(self):
        """Return the AR account."""
        account = self.env['accounting.account'].search(
            [('code', '=', '110000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'receivable')], limit=1)
        if not account:
            raise UserError(_(
                'No Receivable account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_payment_journal(self):
        """Return an appropriate journal for the payment."""
        if self.payment_method == 'cash':
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'cash')], limit=1)
        else:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'bank')], limit=1)
        if not journal:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'general')], limit=1)
        return journal

    def action_post(self):
        """Override: post original payment, then create accounting move."""
        result = super(sales_payment_accounting, self).action_post()
        self._create_accounting_move()
        return result

    def action_reset_to_draft(self):
        """Override: cancel linked accounting move."""
        for record in self:
            if record.accounting_move_id:
                if record.accounting_move_id.state == 'posted':
                    record.accounting_move_id.action_cancel()
        return super(sales_payment_accounting, self).action_reset_to_draft()

    def _create_accounting_move(self):
        """Create accounting journal entries for this payment.
        Dr Cash/Bank, Cr Accounts Receivable
        """
        self.ensure_one()
        journal = self._get_payment_journal()
        if not journal:
            return

        cash_bank_account = self._get_cash_bank_account()
        receivable_account = self._get_receivable_account()
        partner = (
            self.customer_id.partner_id
            if self.customer_id and self.customer_id.partner_id
            else False
        )

        lines = [
            (0, 0, {
                'sequence': 1,
                'account_id': cash_bank_account.id,
                'partner_id': partner.id if partner else False,
                'name': 'Payment: %s — %s' % (
                    self.payment_number,
                    self.memo or ''),
                'debit': self.amount,
                'credit': 0.0,
            }),
            (0, 0, {
                'sequence': 2,
                'account_id': receivable_account.id,
                'partner_id': partner.id if partner else False,
                'name': 'Payment: %s — %s' % (
                    self.payment_number,
                    self.memo or ''),
                'debit': 0.0,
                'credit': self.amount,
                'date_maturity': self.payment_date,
            }),
        ]

        move = self.env['accounting.move'].create({
            'ref': 'Payment: %s' % self.payment_number,
            'date': self.payment_date or fields.Date.today(),
            'journal_id': journal.id,
            'state': 'draft',
            'line_ids': lines,
        })
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass
        self.accounting_move_id = move.id
        return move

    def action_view_accounting_move(self):
        self.ensure_one()
        if not self.accounting_move_id:
            return
        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', 'accounting.move'),
            ('type', '=', 'form'),
        ], limit=1).id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'accounting.move',
            'view_mode': 'form',
            'res_id': self.accounting_move_id.id,
            'views': [(view_id, 'form')],
            'target': 'current',
        }


class purchases_bill_accounting(models.Model):
    _inherit = 'purchases.bill'

    accounting_move_id = fields.Many2one(
        comodel_name='accounting.move', string='Accounting Entry',
        readonly=True, copy=False, ondelete='set null', index=True)
    accounting_move_count = fields.Integer(
        string='Journal Entry Count', compute='_compute_accounting_move_count')

    def _compute_accounting_move_count(self):
        for record in self:
            record.accounting_move_count = 1 if record.accounting_move_id else 0

    def _get_payable_account(self):
        """Return the AP account. Default: account code 220000."""
        account = self.env['accounting.account'].search(
            [('code', '=', '220000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'payable')], limit=1)
        if not account:
            raise UserError(_(
                'No Payable account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_expense_account(self):
        """Return the default expense account. Default: account code 500000."""
        account = self.env['accounting.account'].search(
            [('code', '=', '500000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'expense')], limit=1)
        if not account:
            raise UserError(_(
                'No Expense account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_tax_account(self, tax_id):
        """Return the tax account for a given tax."""
        if tax_id and tax_id.tax_account_id:
            return tax_id.tax_account_id
        account = self.env['accounting.account'].search(
            [('code', '=', '210000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'tax')], limit=1)
        return account

    def _get_purchase_journal(self):
        """Return the Purchase journal."""
        journal = self.env['accounting.journal'].search(
            [('type', '=', 'purchase')], limit=1)
        if not journal:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_(
                'No journal found. Please configure Purchase or General journal.'
            ))
        return journal

    def action_post(self):
        """Override: post original bill, then create accounting move."""
        result = super(purchases_bill_accounting, self).action_post()
        self._create_accounting_move()
        return result

    def action_reset_to_draft(self):
        """Override: cancel linked accounting move."""
        for record in self:
            if record.accounting_move_id:
                if record.accounting_move_id.state == 'posted':
                    record.accounting_move_id.action_cancel()
        return super(purchases_bill_accounting, self).action_reset_to_draft()

    def _create_accounting_move(self):
        """Create accounting journal entries for this vendor bill.
        Dr Expense lines, Dr Tax, Cr Accounts Payable
        """
        self.ensure_one()
        journal = self._get_purchase_journal()
        payable_account = self._get_payable_account()
        expense_account = self._get_expense_account()

        lines = []
        seq = 1
        total_expense = 0.0
        total_tax = 0.0

        vendor = self.vendor_id
        partner = vendor.partner_id if vendor and vendor.partner_id else False

        # --- 1. Expense lines (debit each line total) ---
        for line in self.line_ids.sorted('id'):
            if not line.total:
                continue
            total_expense += line.sub_total
            # Resolve per-line account: product category > default expense account
            line_account = expense_account
            if line.product_id and line.product_id.product_category:
                cat = line.product_id.product_category
                if cat.expense_account_id:
                    line_account = cat.expense_account_id
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': line_account.id,
                'partner_id': partner.id if partner else False,
                'name': line.description or 'Bill Line',
                'debit': line.sub_total,
                'credit': 0.0,
            }))
            seq += 1

        # --- 2. Tax lines (debit) ---
        grouped_taxes = {}
        for line in self.line_ids:
            if not line.tax_amount:
                continue
            tax = line.tax_id
            tax_key = tax.id if tax else 0
            if tax_key not in grouped_taxes:
                tax_account = self._get_tax_account(tax)
                grouped_taxes[tax_key] = {
                    'name': tax.name if tax else 'Tax',
                    'amount': 0.0,
                    'account_id': tax_account.id if tax_account else False,
                }
            grouped_taxes[tax_key]['amount'] += line.tax_amount
            total_tax += line.tax_amount

        for tax_data in grouped_taxes.values():
            if not tax_data['amount'] or not tax_data['account_id']:
                continue
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': tax_data['account_id'],
                'partner_id': partner.id if partner else False,
                'name': tax_data['name'],
                'debit': tax_data['amount'],
                'credit': 0.0,
            }))
            seq += 1

        # --- 3. Payable line (credit total) ---
        total = total_expense + total_tax
        if not total:
            # If no line data, use the bill's total
            total = self.amount_total or 0.0

        if total:
            due_date = (
                self.due_date
                or (self.bill_date + timedelta(days=30) if self.bill_date
                    else fields.Date.today())
            )
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': payable_account.id,
                'partner_id': partner.id if partner else False,
                'name': 'Bill: %s' % self.bill_number,
                'debit': 0.0,
                'credit': total,
                'date_maturity': due_date,
            }))
            seq += 1

        if not lines:
            return

        move = self.env['accounting.move'].create({
            'ref': 'Bill: %s' % (self.bill_number or ''),
            'date': self.bill_date or fields.Date.today(),
            'journal_id': journal.id,
            'state': 'draft',
            'line_ids': lines,
        })
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass
        self.accounting_move_id = move.id
        return move

    def action_view_accounting_move(self):
        self.ensure_one()
        if not self.accounting_move_id:
            return
        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', 'accounting.move'),
            ('type', '=', 'form'),
        ], limit=1).id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'accounting.move',
            'view_mode': 'form',
            'res_id': self.accounting_move_id.id,
            'views': [(view_id, 'form')],
            'target': 'current',
        }


class purchases_payment_register_accounting(models.TransientModel):
    _inherit = 'purchases.payment.register'

    def _get_cash_bank_account(self):
        """Return the cash/bank account used to pay vendor bills."""
        account = self.env['accounting.account'].search(
            [('code', '=', '100000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', 'in', ['bank', 'cash'])], limit=1)
        if not account:
            raise UserError(_(
                'No Cash/Bank account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_payable_account(self):
        """Return the AP account used by vendor bill payments."""
        account = self.env['accounting.account'].search(
            [('code', '=', '220000')], limit=1)
        if not account:
            account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'payable')], limit=1)
        if not account:
            raise UserError(_(
                'No Payable account found. '
                'Please configure Chart of Accounts.'
            ))
        return account

    def _get_payment_journal(self):
        """Return an appropriate journal for vendor bill payment."""
        journal = self.env['accounting.journal'].search(
            [('type', '=', 'bank')], limit=1)
        if not journal:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'cash')], limit=1)
        if not journal:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_(
                'No journal found. Please configure Bank, Cash, or General journal.'
            ))
        return journal

    def _create_accounting_move(self):
        """Create accounting journal entries for vendor bill payment.
        Dr Accounts Payable, Cr Cash/Bank.
        """
        self.ensure_one()
        bill = self.bill_id
        journal = self._get_payment_journal()
        payable_account = self._get_payable_account()
        cash_bank_account = self._get_cash_bank_account()
        partner = (
            bill.vendor_id.partner_id
            if bill.vendor_id and bill.vendor_id.partner_id
            else False
        )
        label = self.memo or bill.bill_number

        move = self.env['accounting.move'].create({
            'ref': 'Vendor Payment: %s' % (bill.bill_number or ''),
            'date': self.payment_date or fields.Date.today(),
            'journal_id': journal.id,
            'state': 'draft',
            'line_ids': [
                (0, 0, {
                    'sequence': 1,
                    'account_id': payable_account.id,
                    'partner_id': partner.id if partner else False,
                    'name': 'Vendor Payment: %s' % label,
                    'debit': self.amount,
                    'credit': 0.0,
                    'date_maturity': self.payment_date,
                }),
                (0, 0, {
                    'sequence': 2,
                    'account_id': cash_bank_account.id,
                    'partner_id': partner.id if partner else False,
                    'name': 'Vendor Payment: %s' % label,
                    'debit': 0.0,
                    'credit': self.amount,
                }),
            ],
        })
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass
        return move

    def action_confirm_payment(self):
        result = super(purchases_payment_register_accounting,
                       self).action_confirm_payment()
        for wizard in self:
            wizard._create_accounting_move()
        return result


# =============================================================================
# GROUP E: WIZARD MODELS
# =============================================================================

class accounting_trial_balance_wizard(models.TransientModel):
    _name = 'accounting.trial.balance.wizard'
    _description = 'Trial Balance Wizard'

    date_from = fields.Date(
        string='Start Date', required=True,
        default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        string='End Date', required=True,
        default=fields.Date.today)
    target_move = fields.Selection([
        ('posted', 'Posted Entries'),
        ('all', 'All Entries'),
    ], string='Target Moves', default='posted', required=True)

    def action_generate(self):
        self.ensure_one()
        return {
            'name': _('Trial Balance'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.trial.balance.report',
            'view_mode': 'tree',
            'views': [(False, 'tree')],
            'target': 'current',
            'context': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'target_move': self.target_move,
            },
        }


class accounting_general_ledger_wizard(models.TransientModel):
    _name = 'accounting.general.ledger.wizard'
    _description = 'General Ledger Wizard'

    date_from = fields.Date(
        string='Start Date', required=True,
        default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        string='End Date', required=True,
        default=fields.Date.today)
    account_ids = fields.Many2many(
        comodel_name='accounting.account', string='Accounts',
        domain=[('active', '=', True)])
    target_move = fields.Selection([
        ('posted', 'Posted Entries'),
        ('all', 'All Entries'),
    ], string='Target Moves', default='posted', required=True)

    def action_generate(self):
        self.ensure_one()
        return {
            'name': _('General Ledger'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.general.ledger.report',
            'view_mode': 'tree',
            'views': [(False, 'tree')],
            'target': 'current',
            'context': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'account_ids': self.account_ids.ids,
                'target_move': self.target_move,
            },
        }


class accounting_aged_receivable_wizard(models.TransientModel):
    _name = 'accounting.aged.receivable.wizard'
    _description = 'Aged Receivable Wizard'

    date_as_of = fields.Date(
        string='Date As Of', required=True,
        default=fields.Date.today)
    period_length = fields.Selection([
        ('30', '30 Days'),
        ('60', '60 Days'),
        ('90', '90 Days'),
    ], string='Period Length', default='30', required=True)

    def action_generate(self):
        self.ensure_one()
        return {
            'name': _('Aged Receivable'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.aged.receivable.report',
            'view_mode': 'tree',
            'views': [(False, 'tree')],
            'target': 'current',
            'context': {
                'date_as_of': self.date_as_of,
                'period_length': int(self.period_length),
            },
        }


# =============================================================================
# GROUP F: REPORT MODELS (SQL Views)
# =============================================================================

class accounting_trial_balance_report(models.Model):
    _name = 'accounting.trial.balance.report'
    _description = 'Trial Balance Report'
    _auto = False
    _rec_name = 'account_code'
    _order = 'account_code'

    account_id = fields.Many2one('accounting.account', readonly=True)
    account_code = fields.Char(readonly=True)
    account_name = fields.Char(readonly=True)
    type_name = fields.Char(readonly=True)
    total_debit = fields.Float(readonly=True, digits=(16, 0))
    total_credit = fields.Float(readonly=True, digits=(16, 0))
    balance = fields.Float(readonly=True, digits=(16, 0))

    def init(self):
        self.env.cr.execute(
            "DROP VIEW IF EXISTS %s CASCADE" % (self._table,))
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY a.code) AS id,
                    a.id AS account_id,
                    a.code AS account_code,
                    a.name AS account_name,
                    at.name AS type_name,
                    COALESCE(SUM(ml.debit), 0.0) AS total_debit,
                    COALESCE(SUM(ml.credit), 0.0) AS total_credit,
                    COALESCE(SUM(ml.debit) - SUM(ml.credit), 0.0) AS balance
                FROM accounting_account a
                LEFT JOIN accounting_account_type at ON at.id = a.type_id
                LEFT JOIN accounting_move_line ml ON ml.account_id = a.id
                LEFT JOIN accounting_move m ON m.id = ml.move_id
                WHERE a.active = TRUE
                  AND (
                      m.state = 'posted'
                      OR m.id IS NULL
                  )
                GROUP BY a.id, a.code, a.name, at.name
                ORDER BY a.code
            )
        """ % (self._table,))


class accounting_general_ledger_report(models.Model):
    _name = 'accounting.general.ledger.report'
    _description = 'General Ledger Report'
    _auto = False
    _order = 'move_date, account_code, sequence'

    move_id = fields.Many2one('accounting.move', readonly=True)
    move_name = fields.Char(readonly=True)
    move_date = fields.Date(readonly=True)
    journal_name = fields.Char(readonly=True)
    account_id = fields.Many2one('accounting.account', readonly=True)
    account_code = fields.Char(readonly=True)
    account_name = fields.Char(readonly=True)
    sequence = fields.Integer(readonly=True)
    line_name = fields.Char(readonly=True)
    partner_name = fields.Char(readonly=True)
    debit = fields.Float(readonly=True, digits=(16, 0))
    credit = fields.Float(readonly=True, digits=(16, 0))
    ref = fields.Char(readonly=True)

    def init(self):
        self.env.cr.execute(
            "DROP VIEW IF EXISTS %s CASCADE" % (self._table,))
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY m.date, a.code, ml.sequence, ml.id
                    ) AS id,
                    m.id AS move_id,
                    m.name AS move_name,
                    m.date AS move_date,
                    j.name AS journal_name,
                    a.id AS account_id,
                    a.code AS account_code,
                    a.name AS account_name,
                    ml.sequence AS sequence,
                    ml.name AS line_name,
                    rp.name AS partner_name,
                    ml.debit AS debit,
                    ml.credit AS credit,
                    m.ref AS ref
                FROM accounting_move_line ml
                JOIN accounting_account a ON a.id = ml.account_id
                JOIN accounting_move m ON m.id = ml.move_id
                JOIN accounting_journal j ON j.id = m.journal_id
                LEFT JOIN res_partner rp ON rp.id = ml.partner_id
                WHERE m.state = 'posted'
                ORDER BY m.date, a.code, ml.sequence, ml.id
            )
        """ % (self._table,))


class accounting_aged_receivable_report(models.Model):
    _name = 'accounting.aged.receivable.report'
    _description = 'Aged Receivable Report'
    _auto = False
    _order = 'partner_name'

    partner_id = fields.Many2one('res.partner', readonly=True)
    partner_name = fields.Char(readonly=True)
    total = fields.Float(readonly=True, digits=(16, 0))
    age_0_30 = fields.Float(readonly=True, digits=(16, 0))
    age_31_60 = fields.Float(readonly=True, digits=(16, 0))
    age_61_90 = fields.Float(readonly=True, digits=(16, 0))
    age_90_plus = fields.Float(readonly=True, digits=(16, 0))

    def init(self):
        self.env.cr.execute(
            "DROP VIEW IF EXISTS %s CASCADE" % (self._table,))
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY rp.name) AS id,
                    rp.id AS partner_id,
                    rp.name AS partner_name,
                    COALESCE(SUM(ml.debit - ml.credit), 0.0) AS total,
                    COALESCE(SUM(
                        CASE WHEN ml.date_maturity IS NULL
                              OR ml.date_maturity >= CURRENT_DATE
                              OR (CURRENT_DATE - ml.date_maturity) <= 30
                        THEN ml.debit - ml.credit ELSE 0.0 END
                    ), 0.0) AS age_0_30,
                    COALESCE(SUM(
                        CASE WHEN ml.date_maturity IS NOT NULL
                              AND (CURRENT_DATE - ml.date_maturity) > 30
                              AND (CURRENT_DATE - ml.date_maturity) <= 60
                        THEN ml.debit - ml.credit ELSE 0.0 END
                    ), 0.0) AS age_31_60,
                    COALESCE(SUM(
                        CASE WHEN ml.date_maturity IS NOT NULL
                              AND (CURRENT_DATE - ml.date_maturity) > 60
                              AND (CURRENT_DATE - ml.date_maturity) <= 90
                        THEN ml.debit - ml.credit ELSE 0.0 END
                    ), 0.0) AS age_61_90,
                    COALESCE(SUM(
                        CASE WHEN ml.date_maturity IS NOT NULL
                              AND (CURRENT_DATE - ml.date_maturity) > 90
                        THEN ml.debit - ml.credit ELSE 0.0 END
                    ), 0.0) AS age_90_plus
                FROM accounting_move_line ml
                JOIN accounting_account a ON a.id = ml.account_id
                JOIN accounting_account_type at ON at.id = a.type_id
                JOIN accounting_move m ON m.id = ml.move_id
                JOIN res_partner rp ON rp.id = ml.partner_id
                WHERE m.state = 'posted'
                  AND at.code = 'receivable'
                  AND ml.reconciled = FALSE
                  AND ml.partner_id IS NOT NULL
                GROUP BY rp.id, rp.name
                HAVING COALESCE(SUM(ml.debit - ml.credit), 0.0) != 0.0
                ORDER BY rp.name
            )
        """ % (self._table,))


class accounting_balance_sheet_wizard(models.TransientModel):
    _name = 'accounting.balance.sheet.wizard'
    _description = 'Balance Sheet Wizard'

    date_as_of = fields.Date(
        string='As Of Date', required=True,
        default=fields.Date.today)
    target_move = fields.Selection([
        ('posted', 'Posted Entries'),
        ('all', 'All Entries'),
    ], string='Target Moves', default='posted', required=True)

    def action_generate(self):
        self.ensure_one()
        report_data = self.env['accounting.balance.sheet.report'].search([])
        report = self.env.ref(
            'accounting.action_report_balance_sheet')
        return report.with_context(
            date_as_of=self.date_as_of,
        ).report_action(report_data)


class accounting_balance_sheet_report(models.Model):
    _name = 'accounting.balance.sheet.report'
    _description = 'Balance Sheet Report'
    _auto = False
    _rec_name = 'account_name'
    _order = 'category_order, subcategory_order, account_code'

    account_id = fields.Many2one('accounting.account', readonly=True)
    account_code = fields.Char(readonly=True)
    account_name = fields.Char(readonly=True)
    type_name = fields.Char(readonly=True)
    category = fields.Char(readonly=True)
    category_order = fields.Integer(readonly=True)
    subcategory = fields.Char(readonly=True)
    subcategory_order = fields.Integer(readonly=True)
    balance = fields.Float(readonly=True, digits=(16, 0))

    def init(self):
        self.env.cr.execute(
            "DROP VIEW IF EXISTS %s CASCADE" % (self._table,))
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH net_income AS (
                    SELECT
                        COALESCE(SUM(CASE WHEN at2.code = 'income'
                                          THEN ml2.credit - ml2.debit
                                          ELSE 0.0 END), 0.0)
                        - COALESCE(SUM(CASE WHEN at2.code = 'expense'
                                            THEN ml2.debit - ml2.credit
                                            ELSE 0.0 END), 0.0)
                        AS amount
                    FROM accounting_move_line ml2
                    JOIN accounting_account a2 ON a2.id = ml2.account_id
                    JOIN accounting_account_type at2 ON at2.id = a2.type_id
                    JOIN accounting_move m2 ON m2.id = ml2.move_id
                    WHERE m2.state = 'posted'
                      AND at2.code IN ('income', 'expense')
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY
                        CASE WHEN at.code IN ('bank','cash','current_asset',
                                               'prepayment','receivable') THEN 1
                             WHEN at.code = 'fixed_asset' THEN 1
                             WHEN at.code IN ('payable','liability','tax') THEN 2
                             ELSE 3 END,
                        CASE WHEN at.code IN ('bank','cash','current_asset',
                                               'prepayment','receivable') THEN 1
                             WHEN at.code = 'fixed_asset' THEN 2
                             ELSE 0 END,
                        a.code) AS id,
                    a.id AS account_id,
                    a.code AS account_code,
                    CASE WHEN a.code = '310000'
                         THEN 'Retained Earnings (incl. Net Profit)'
                         ELSE a.name
                    END AS account_name,
                    at.name AS type_name,
                    CASE WHEN at.code IN ('bank','cash','current_asset','fixed_asset',
                                           'prepayment','receivable') THEN 'Assets'
                         WHEN at.code IN ('payable','liability','tax') THEN 'Liabilities'
                         ELSE 'Equity' END AS category,
                    CASE WHEN at.code IN ('bank','cash','current_asset','fixed_asset',
                                           'prepayment','receivable') THEN 1
                         WHEN at.code IN ('payable','liability','tax') THEN 2
                         ELSE 3 END AS category_order,
                    CASE WHEN at.code IN ('bank','cash','current_asset',
                                           'prepayment','receivable') THEN 'Current Asset'
                         WHEN at.code = 'fixed_asset' THEN 'Fixed Asset'
                         ELSE '' END AS subcategory,
                    CASE WHEN at.code IN ('bank','cash','current_asset',
                                           'prepayment','receivable') THEN 1
                         WHEN at.code = 'fixed_asset' THEN 2
                         ELSE 0 END AS subcategory_order,
                    CASE WHEN at.code IN ('bank','cash','current_asset','fixed_asset',
                                           'prepayment','receivable')
                         THEN COALESCE(ml_agg.total_debit, 0.0)
                              - COALESCE(ml_agg.total_credit, 0.0)
                         WHEN a.code = '310000'
                         THEN COALESCE(ml_agg.total_credit, 0.0)
                              - COALESCE(ml_agg.total_debit, 0.0)
                              + COALESCE(ni.amount, 0.0)
                         ELSE COALESCE(ml_agg.total_credit, 0.0)
                              - COALESCE(ml_agg.total_debit, 0.0)
                    END AS balance
                FROM accounting_account a
                JOIN accounting_account_type at ON at.id = a.type_id
                CROSS JOIN net_income ni
                LEFT JOIN (
                    SELECT ml.account_id,
                           SUM(ml.debit) AS total_debit,
                           SUM(ml.credit) AS total_credit
                    FROM accounting_move_line ml
                    JOIN accounting_move m ON m.id = ml.move_id
                    WHERE m.state = 'posted'
                    GROUP BY ml.account_id
                ) ml_agg ON ml_agg.account_id = a.id
                WHERE a.active = TRUE
                  AND at.code IN ('bank','cash','current_asset','fixed_asset',
                                   'prepayment','receivable','payable','liability','tax','equity')
                ORDER BY category_order, subcategory_order, a.code
            )
        """ % (self._table,))


class accounting_profit_loss_wizard(models.TransientModel):
    _name = 'accounting.profit.loss.wizard'
    _description = 'Profit And Loss Wizard'

    date_from = fields.Date(
        string='Start Date', required=True,
        default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        string='End Date', required=True,
        default=fields.Date.today)
    target_move = fields.Selection([
        ('posted', 'Posted Entries'),
        ('all', 'All Entries'),
    ], string='Target Moves', default='posted', required=True)

    def action_generate(self):
        self.ensure_one()
        report_data = self.env['accounting.profit.loss.report'].search([])
        report = self.env.ref(
            'accounting.action_report_profit_loss')
        return report.with_context(
            date_from=self.date_from,
            date_to=self.date_to,
        ).report_action(report_data)


class accounting_profit_loss_report(models.Model):
    _name = 'accounting.profit.loss.report'
    _description = 'Profit And Loss Report'
    _auto = False
    _rec_name = 'account_name'
    _order = 'category_order, account_code'

    account_id = fields.Many2one('accounting.account', readonly=True)
    account_code = fields.Char(readonly=True)
    account_name = fields.Char(readonly=True)
    type_name = fields.Char(readonly=True)
    category = fields.Char(readonly=True)
    category_order = fields.Integer(readonly=True)
    balance = fields.Float(readonly=True, digits=(16, 0))

    def init(self):
        self.env.cr.execute(
            "DROP VIEW IF EXISTS %s CASCADE" % (self._table,))
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY
                        CASE WHEN at.code = 'income' THEN 1 ELSE 2 END,
                        a.code) AS id,
                    a.id AS account_id,
                    a.code AS account_code,
                    a.name AS account_name,
                    at.name AS type_name,
                    CASE WHEN at.code = 'income' THEN 'Revenue' ELSE 'Expenses' END AS category,
                    CASE WHEN at.code = 'income' THEN 1 ELSE 2 END AS category_order,
                    CASE WHEN at.code = 'income'
                         THEN COALESCE(ml_agg.total_credit, 0.0)
                              - COALESCE(ml_agg.total_debit, 0.0)
                         ELSE COALESCE(ml_agg.total_debit, 0.0)
                              - COALESCE(ml_agg.total_credit, 0.0)
                    END AS balance
                FROM accounting_account a
                JOIN accounting_account_type at ON at.id = a.type_id
                LEFT JOIN (
                    SELECT ml.account_id,
                           SUM(ml.debit) AS total_debit,
                           SUM(ml.credit) AS total_credit
                    FROM accounting_move_line ml
                    JOIN accounting_move m ON m.id = ml.move_id
                    WHERE m.state = 'posted'
                    GROUP BY ml.account_id
                ) ml_agg ON ml_agg.account_id = a.id
                WHERE a.active = TRUE
                  AND at.code IN ('income', 'expense')
                ORDER BY category_order, a.code
            )
        """ % (self._table,))


# ===================================================================
# COMMISSION PLANS
# ===================================================================


class accounting_commission_plan(models.Model):
    _name = 'accounting.commission.plan'
    _inherit = ['navigation.mixin']
    _description = 'Commission Plan'
    _rec_name = 'name'
    _menu_code = 'commission_plans'

    name = fields.Char(string='Plan Name', required=True)
    code = fields.Char(string='Code', readonly=True, copy=False)
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ], string='Type', default='percentage', required=True)
    rate = fields.Float(string='Rate (%) / Amount', required=True, digits=(16, 2))
    based_on = fields.Selection([
        ('untaxed', 'Untaxed Amount'),
        ('total', 'Total Amount'),
    ], string='Based On', default='untaxed', required=True)
    journal_id = fields.Many2one(
        'accounting.journal', string='Journal',
        domain=[('type', '=', 'general')],
        help='Journal used for commission entries.')
    expense_account_id = fields.Many2one(
        'accounting.account', string='Expense Account',
        domain=[('type_id.code', '=', 'expense')])
    payable_account_id = fields.Many2one(
        'accounting.account', string='Payable Account',
        domain=[('type_id.code', 'in', ['payable', 'liability'])])
    active = fields.Boolean(default=True)
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code(
                'accounting.commission.plan') or '/'
        return super(accounting_commission_plan, self).create(vals)


class accounting_commission_settlement(models.Model):
    _name = 'accounting.commission.settlement'
    _inherit = ['navigation.mixin']
    _description = 'Commission Settlement'
    _rec_name = 'name'
    _menu_code = 'commission_settlements'

    name = fields.Char(string='Reference', readonly=True, copy=False)
    invoice_id = fields.Many2one(
        'sales.invoice', string='Invoice', readonly=True, ondelete='restrict')
    salesperson_id = fields.Many2one(
        'general.custom_users', string='Salesperson', readonly=True)
    plan_id = fields.Many2one(
        'accounting.commission.plan', string='Commission Plan', readonly=True)
    date = fields.Date(string='Date', default=fields.Date.today, readonly=True)
    base_amount = fields.Float(string='Base Amount', digits=(16, 0), readonly=True)
    rate = fields.Float(string='Rate (%)', digits=(16, 2), readonly=True)
    commission_amount = fields.Float(
        string='Commission Amount', digits=(16, 0), readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')
    move_id = fields.Many2one(
        'accounting.move', string='Journal Entry', readonly=True, copy=False)
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'accounting.commission.settlement') or '/'
        return super(accounting_commission_settlement, self).create(vals)

    def action_post(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft settlements can be posted.'))
        self._create_accounting_move()
        self.write({'state': 'posted'})

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'draft':
            self.write({'state': 'cancel'})
        elif self.state == 'posted':
            if self.move_id and self.move_id.state == 'posted':
                self.move_id.action_cancel()
            self.write({'state': 'cancel'})

    def _create_accounting_move(self):
        self.ensure_one()
        if not self.plan_id.journal_id:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'general')], limit=1)
            if not journal:
                raise UserError(
                    _('No general journal found. Please configure one.'))
        else:
            journal = self.plan_id.journal_id

        expense_account = self.plan_id.expense_account_id
        if not expense_account:
            expense_account = self.env['accounting.account'].search(
                [('code', '=', '510000')], limit=1)
        if not expense_account:
            expense_account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'expense')], limit=1)
        if not expense_account:
            raise UserError(
                _('No expense account found for commission.'))

        payable_account = self.plan_id.payable_account_id
        if not payable_account:
            payable_account = self.env['accounting.account'].search(
                [('code', '=', '220000')], limit=1)
        if not payable_account:
            payable_account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'payable')], limit=1)
        if not payable_account:
            payable_account = self.env['accounting.account'].search(
                [('type_id.code', '=', 'liability')], limit=1)
        if not payable_account:
            raise UserError(
                _('No payable account found for commission.'))

        move_lines = [
            (0, 0, {
                'account_id': expense_account.id,
                'name': 'Commission: %s' % self.name,
                'debit': self.commission_amount,
                'credit': 0.0,
                'partner_id': self.invoice_id.customer_id.partner_id.id if self.invoice_id.customer_id and self.invoice_id.customer_id.partner_id else False,
            }),
            (0, 0, {
                'account_id': payable_account.id,
                'name': 'Commission Payable: %s' % self.name,
                'debit': 0.0,
                'credit': self.commission_amount,
                'partner_id': self.salesperson_id.partner_id.id if self.salesperson_id.partner_id else False,
            }),
        ]

        move = self.env['accounting.move'].create({
            'ref': 'Commission: %s - %s' % (self.name, self.salesperson_id.name if self.salesperson_id else ''),
            'date': self.date or fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': move_lines,
        })
        move.action_post()
        self.write({'move_id': move.id})

    def action_view_move(self):
        self.ensure_one()
        return {
            'name': _('Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.move',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_id': self.move_id.id,
            'target': 'current',
        }


class sales_delivery_accounting(models.Model):
    _inherit = 'sales.delivery'

    @api.model_create_multi
    def create(self, vals_list):
        deliveries = super(sales_delivery_accounting, self).create(vals_list)
        for delivery in deliveries:
            if delivery.state == 'done':
                delivery._create_cogs_accounting_move()
        return deliveries

    def write(self, vals):
        previous_states = {d.id: d.state for d in self}
        result = super(sales_delivery_accounting, self).write(vals)
        if vals.get('state') == 'done':
            for delivery in self:
                if previous_states.get(delivery.id) != 'done':
                    delivery._create_cogs_accounting_move()
        return result

    def _create_cogs_accounting_move(self):
        self.ensure_one()
        journal = self.env['accounting.journal'].search(
            [('type', '=', 'general')], limit=1)
        if not journal:
            return

        lines = []
        seq = 1
        for dline in self.line_ids:
            if not dline.product_id or not dline.product_id.product_category:
                continue
            cat = dline.product_id.product_category
            if not cat.expense_account_id or not cat.stock_account_id:
                continue
            cogs_amount = (dline.quantity or 0) * dline.product_id.price
            if cogs_amount <= 0:
                continue
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': cat.expense_account_id.id,
                'name': 'COGS: %s' % (dline.description or 'Delivery Line'),
                'debit': cogs_amount,
                'credit': 0.0,
            }))
            seq += 1
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': cat.stock_account_id.id,
                'name': 'COGS: %s' % (dline.description or 'Delivery Line'),
                'debit': 0.0,
                'credit': cogs_amount,
            }))
            seq += 1

        if not lines:
            return

        move = self.env['accounting.move'].create({
            'ref': 'COGS: %s' % self.delivery_number,
            'date': self.delivery_date or fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': lines,
        })
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass


class purchases_receipt_accounting(models.Model):
    _inherit = 'purchases.receipt'

    @api.model_create_multi
    def create(self, vals_list):
        receipts = super(purchases_receipt_accounting, self).create(vals_list)
        for receipt in receipts:
            if receipt.state == 'received':
                receipt._create_receipt_accounting_move()
        return receipts

    def write(self, vals):
        previous_states = {r.id: r.state for r in self}
        result = super(purchases_receipt_accounting, self).write(vals)
        if vals.get('state') == 'received':
            for receipt in self:
                if previous_states.get(receipt.id) != 'received':
                    receipt._create_receipt_accounting_move()
        return result

    def _create_receipt_accounting_move(self):
        self.ensure_one()
        journal = self.env['accounting.journal'].search(
            [('type', '=', 'purchase')], limit=1)
        if not journal:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_(
                'No purchase or general journal found. '
                'Please configure a journal first.'
            ))

        interim_account = self.env['accounting.account'].search(
            [('code', '=', '113200')], limit=1)
        if not interim_account:
            raise UserError(_(
                'Account 113200 (Stock Interim Received) not found. '
                'Please add it to the Chart of Accounts.'
            ))

        lines = []
        seq = 1
        for rline in self.line_ids:
            if not rline.product_id or not rline.product_id.product_category:
                continue
            cat = rline.product_id.product_category
            if not cat.stock_account_id:
                continue
            amount = (rline.quantity or 0) * rline.product_id.price
            if amount <= 0:
                continue
            # Dr Stock Account
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': cat.stock_account_id.id,
                'name': 'Goods Received: %s' % (rline.description or 'Receipt Line'),
                'debit': amount,
                'credit': 0.0,
            }))
            seq += 1
            # Cr Stock Interim Received
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': interim_account.id,
                'name': 'Goods Received: %s' % (rline.description or 'Receipt Line'),
                'debit': 0.0,
                'credit': amount,
            }))
            seq += 1

        if not lines:
            return

        move = self.env['accounting.move'].create({
            'ref': 'Receipt: %s' % self.receipt_number,
            'date': self.receipt_date or fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': lines,
        })
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass


class purchases_bill_accounting_interim(models.Model):
    _inherit = 'purchases.bill'

    def _create_accounting_move(self):
        """Override: use Stock Interim Received instead of Expense for purchase bills.
        Dr Stock Interim Received / Cr Accounts Payable."""
        self.ensure_one()
        journal = self._get_purchase_journal()
        payable_account = self._get_payable_account()

        interim_account = self.env['accounting.account'].search(
            [('code', '=', '113200')], limit=1)

        lines = []
        seq = 1
        total_debit = 0.0
        total_tax = 0.0

        vendor = self.vendor_id
        partner = vendor.partner_id if vendor and vendor.partner_id else False

        # --- 1. Interim Received lines (debit) ---
        for line in self.line_ids.sorted('id'):
            if not line.total:
                continue
            total_debit += line.sub_total
            line_account = interim_account if interim_account else self._get_expense_account()
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': line_account.id,
                'partner_id': partner.id if partner else False,
                'name': line.description or 'Bill Line',
                'debit': line.sub_total,
                'credit': 0.0,
            }))
            seq += 1

        # --- 2. Tax lines (debit) ---
        grouped_taxes = {}
        for line in self.line_ids:
            if not line.tax_amount:
                continue
            tax = line.tax_id
            tax_key = tax.id if tax else 0
            if tax_key not in grouped_taxes:
                tax_account = self._get_tax_account(tax)
                grouped_taxes[tax_key] = {
                    'name': tax.name if tax else 'Tax',
                    'amount': 0.0,
                    'account_id': tax_account.id if tax_account else False,
                }
            grouped_taxes[tax_key]['amount'] += line.tax_amount
            total_tax += line.tax_amount

        for tax_data in grouped_taxes.values():
            if not tax_data['amount'] or not tax_data['account_id']:
                continue
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': tax_data['account_id'],
                'partner_id': partner.id if partner else False,
                'name': tax_data['name'],
                'debit': tax_data['amount'],
                'credit': 0.0,
            }))
            seq += 1

        # --- 3. Payable line (credit) ---
        total = total_debit + total_tax
        if not total:
            total = self.amount_total or 0.0

        if total:
            due_date = (
                self.due_date
                or (self.bill_date + timedelta(days=30) if self.bill_date
                    else fields.Date.today())
            )
            lines.append((0, 0, {
                'sequence': seq,
                'account_id': payable_account.id,
                'partner_id': partner.id if partner else False,
                'name': 'Bill: %s' % self.bill_number,
                'debit': 0.0,
                'credit': total,
                'date_maturity': due_date,
            }))
            seq += 1

        if not lines:
            return

        move = self.env['accounting.move'].create({
            'ref': 'Bill: %s' % (self.bill_number or ''),
            'date': self.bill_date or fields.Date.today(),
            'journal_id': journal.id,
            'state': 'draft',
            'line_ids': lines,
        })
        if move.is_balanced:
            try:
                move.action_post()
            except UserError:
                pass
        self.accounting_move_id = move.id
        return move


class product_category_account(models.Model):
    _inherit = 'sales.product_category'

    income_account_id = fields.Many2one(
        'accounting.account', string='Income Account', required=True,
        help='Revenue account for products in this category.')
    expense_account_id = fields.Many2one(
        'accounting.account', string='Expense Account',
        help='Expense account for products in this category.')
    stock_account_id = fields.Many2one(
        'accounting.account', string='Stock Account',
        help='Stock/inventory account for products in this category.')

    @api.constrains('expense_account_id', 'stock_account_id')
    def _check_expense_stock_accounts(self):
        for rec in self:
            if rec.expense_account_id and not rec.stock_account_id:
                raise ValidationError(_(
                    'Stock Account is required when Expense Account is set.'
                ))
            if rec.stock_account_id and not rec.expense_account_id:
                raise ValidationError(_(
                    'Expense Account is required when Stock Account is set.'
                ))


class sales_invoice_commission(models.Model):
    _inherit = 'sales.invoice'

    commission_settlement_ids = fields.One2many(
        'accounting.commission.settlement', 'invoice_id',
        string='Commission Settlements', copy=False)
    commission_amount = fields.Float(
        string='Commission', compute='_compute_commission',
        store=True, digits=(16, 0))
    commission_count = fields.Integer(
        string='Commission Count', compute='_compute_commission_count')

    @api.depends('commission_settlement_ids.commission_amount',
                 'commission_settlement_ids.state')
    def _compute_commission(self):
        for rec in self:
            posted = rec.commission_settlement_ids.filtered(
                lambda s: s.state == 'posted')
            rec.commission_amount = sum(posted.mapped('commission_amount'))

    def _compute_commission_count(self):
        for rec in self:
            rec.commission_count = len(rec.commission_settlement_ids)

    def action_view_commission_settlements(self):
        self.ensure_one()
        return {
            'name': _('Commission Settlements'),
            'type': 'ir.actions.act_window',
            'res_model': 'accounting.commission.settlement',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'target': 'current',
        }
