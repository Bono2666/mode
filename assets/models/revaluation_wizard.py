# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class revaluation_wizard(models.TransientModel):
    _name = 'assets.revaluation_wizard'
    _description = 'Asset Revaluation Wizard'

    asset_id = fields.Many2one(
        'assets.asset', string='Asset', required=True, ondelete='cascade',
        readonly=True)
    asset_number = fields.Char(
        related='asset_id.asset_number', string='Asset Number', readonly=True)
    asset_name = fields.Char(
        related='asset_id.name', string='Asset Name', readonly=True)
    book_value_current = fields.Float(
        related='asset_id.book_value', string='Current Book Value',
        readonly=True, digits=(16, 0))
    fair_value_new = fields.Float(
        string='New Fair Value', required=True, digits=(16, 0))
    revaluation_date = fields.Date(
        string='Revaluation Date', required=True, default=fields.Date.today)
    remaining_useful_life = fields.Integer(
        string='Remaining Useful Life (periods)', required=True,
        help='Remaining depreciation periods after this revaluation')
    surplus_deficit = fields.Float(
        string='Surplus / Deficit', compute='_compute_surplus_deficit',
        digits=(16, 0))
    note = fields.Text(string='Justification / Notes')

    @api.depends('fair_value_new', 'book_value_current')
    def _compute_surplus_deficit(self):
        for wiz in self:
            wiz.surplus_deficit = wiz.fair_value_new - wiz.book_value_current

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        if self.asset_id:
            asset = self.asset_id
            remaining_posted = asset.depreciation_line_ids.filtered(
                lambda l: l.state == 'posted')
            total_periods = asset.method_number or 0
            used_periods = len(remaining_posted)
            self.remaining_useful_life = max(total_periods - used_periods, 0)

    def action_confirm_revaluation(self):
        self.ensure_one()
        asset = self.asset_id
        if asset.state not in ('running',):
            raise UserError(_(
                "Revaluation can only be done on running assets."))

        self.env['assets.revaluation_line'].create({
            'asset_id': asset.id,
            'revaluation_date': self.revaluation_date,
            'book_value_before': self.book_value_current,
            'fair_value_after': self.fair_value_new,
            'remaining_useful_life': self.remaining_useful_life,
            'note': self.note or '',
            'state': 'draft',
        })

        reval_line = asset.revaluation_line_ids.filtered(
            lambda r: r.state == 'draft').sorted('revaluation_date')
        if reval_line:
            reval_line[-1].action_post_revaluation()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asset Revalued'),
                'message': _(
                    'Asset %(name)s has been revalued. '
                    'New Fair Value: %(fv)s'
                ) % {
                    'name': asset.name,
                    'fv': f"Rp {self.fair_value_new:,.0f}",
                },
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
