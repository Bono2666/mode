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
             'When a journal entry is posted with a debit to this account, '
             'an asset will be auto-created.')


class accounting_move_asset(models.Model):
    _inherit = 'accounting.move'

    def action_post(self):
        result = super(accounting_move_asset, self).action_post()
        self._create_assets_from_move()
        return result

    def _create_assets_from_move(self):
        for move in self:
            for line in move.line_ids:
                if line.debit <= 0:
                    continue
                if not line.account_id.is_asset_account:
                    continue

                asset_vals = {
                    'name': line.name or 'Auto-created Asset',
                    'state': 'draft',
                    'original_value': line.debit,
                    'acquisition_date': move.date or fields.Date.today(),
                }

                asset = self.env['assets.asset'].create([asset_vals])
                _logger.info(
                    "Auto-created asset %s from JE %s line %s",
                    asset.asset_number, move.name, line.id)
