# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class depreciation_line_accounting(models.Model):
    _inherit = 'assets.depreciation_line'

    def action_post_depreciation(self):
        result = super(depreciation_line_accounting, self).action_post_depreciation()
        return result

    def action_view_move(self):
        result = super(depreciation_line_accounting, self).action_view_move()
        return result

    @api.model
    def action_post_due_entries(self):
        today = fields.Date.today()
        due_lines = self.search([
            ('state', '=', 'draft'),
            ('depreciation_date', '<=', today),
            ('asset_id.state', '=', 'running'),
        ])
        posted_count = 0
        for line in due_lines:
            try:
                line.action_post_depreciation()
                posted_count += 1
            except Exception as e:
                _logger.error(
                    "Failed to post depreciation line %s for asset %s: %s",
                    line.id,
                    line.asset_id.asset_number if line.asset_id else '?',
                    str(e))
        _logger.info(
            "Depreciation cron: posted %d of %d due entries",
            posted_count, len(due_lines))
        return True


class revaluation_line_accounting(models.Model):
    _inherit = 'assets.revaluation_line'

    def action_post_revaluation(self):
        result = super(revaluation_line_accounting, self).action_post_revaluation()
        return result

    def action_view_move(self):
        result = super(revaluation_line_accounting, self).action_view_move()
        return result
