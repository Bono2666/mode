# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class accounting_account_asset(models.Model):
    _inherit = 'accounting.account'

    is_asset_account = fields.Boolean(
        string='Asset Account',
        default=False,
        help='Mark this account as a Fixed Asset account. '
             'When a purchase bill line uses this account, '
             'an asset will be auto-created on bill confirmation.')


class purchases_bill_asset(models.Model):
    _inherit = 'purchases.bill'

    def action_post(self):
        result = super(purchases_bill_asset, self).action_post()
        self._create_assets_from_bill()
        return result

    def _create_assets_from_bill(self):
        self.ensure_one()
        for line in self.line_ids:
            account = False
            if hasattr(line, 'account_id') and line.account_id:
                account = line.account_id
            elif hasattr(line, 'product_id') and line.product_id:
                categ = line.product_id.product_category_id
                if categ and hasattr(categ, 'expense_account_id'):
                    account = categ.expense_account_id

            if not account:
                continue
            if not account.is_asset_account:
                continue

            asset_vals = {
                'name': line.description or 'Auto-created Asset',
                'state': 'draft',
                'original_value': line.sub_total or 0.0,
                'acquisition_date': self.bill_date or fields.Date.today(),
                'purchase_line_id': line.id,
            }

            if line.product_id and hasattr(line.product_id, 'asset_model_id'):
                asset_model = getattr(line.product_id, 'asset_model_id', False)
                if asset_model:
                    asset_vals['asset_model_id'] = asset_model.id
                    asset_vals['method'] = asset_model.method
                    asset_vals['method_number'] = asset_model.method_number
                    asset_vals['method_period'] = asset_model.method_period
                    asset_vals['method_progress_factor'] = asset_model.method_progress_factor
                    asset_vals['prorata_computation_type'] = asset_model.prorata_computation_type
                    if asset_model.account_asset_id:
                        asset_vals['account_asset_id'] = asset_model.account_asset_id.id
                    if asset_model.account_depreciation_id:
                        asset_vals['account_depreciation_id'] = asset_model.account_depreciation_id.id
                    if asset_model.account_depreciation_expense_id:
                        asset_vals['account_depreciation_expense_id'] = asset_model.account_depreciation_expense_id.id
                    if asset_model.journal_id:
                        asset_vals['journal_id'] = asset_model.journal_id.id
            else:
                asset_account = self.env['accounting.account'].search(
                    [('code', '=', '140000')], limit=1)
                if not asset_account:
                    asset_account = self.env['accounting.account'].search(
                        [('type_id.code', '=', 'fixed_asset')], limit=1)
                if asset_account:
                    asset_vals['account_asset_id'] = asset_account.id

                depr_account = self.env['accounting.account'].search(
                    [('code', '=', '141000')], limit=1)
                if not depr_account:
                    depr_account = self.env['accounting.account'].search([
                        ('type_id.code', '=', 'fixed_asset'),
                        ('code', 'like', '14%'),
                    ], limit=1)
                if depr_account and depr_account.id != asset_vals.get('account_asset_id'):
                    asset_vals['account_depreciation_id'] = depr_account.id

                expense_account = self.env['accounting.account'].search(
                    [('code', '=', '520000')], limit=1)
                if not expense_account:
                    expense_account = self.env['accounting.account'].search(
                        [('type_id.code', '=', 'expense')], limit=1)
                if expense_account:
                    asset_vals['account_depreciation_expense_id'] = expense_account.id

                journal = self.env['accounting.journal'].search(
                    [('type', '=', 'general')], limit=1)
                if journal:
                    asset_vals['journal_id'] = journal.id

            asset = self.env['assets.asset'].create(asset_vals)
            _logger.info(
                "Auto-created asset %s from bill %s line %s",
                asset.asset_number, self.bill_number, line.id)
