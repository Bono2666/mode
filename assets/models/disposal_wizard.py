# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class disposal_wizard(models.TransientModel):
    _name = 'assets.disposal_wizard'
    _description = 'Asset Disposal Wizard'

    asset_id = fields.Many2one(
        'assets.asset', string='Asset', required=True, ondelete='cascade',
        readonly=True)
    asset_number = fields.Char(
        related='asset_id.asset_number', string='Asset Number', readonly=True)
    asset_name = fields.Char(
        related='asset_id.name', string='Asset Name', readonly=True)
    book_value = fields.Float(
        related='asset_id.book_value', string='Current Book Value',
        readonly=True, digits=(16, 0))
    sale_price = fields.Float(
        string='Sale / Disposal Price', required=True, digits=(16, 0),
        default=0.0)
    disposal_date = fields.Date(
        string='Disposal Date', required=True, default=fields.Date.today)
    gain_loss = fields.Float(
        string='Gain / Loss', compute='_compute_gain_loss',
        digits=(16, 0))
    note = fields.Text(string='Notes')

    @api.depends('sale_price', 'book_value')
    def _compute_gain_loss(self):
        for wiz in self:
            wiz.gain_loss = wiz.sale_price - wiz.book_value

    def action_confirm_disposal(self):
        self.ensure_one()
        asset = self.asset_id
        if asset.state != 'running':
            raise UserError(_("Only running assets can be disposed."))
        if not asset.account_asset_id:
            raise UserError(_("Asset Account is required."))
        if not asset.account_depreciation_id:
            raise UserError(_("Depreciation Account is required."))

        journal = asset.journal_id
        if not journal:
            journal = self.env['accounting.journal'].search(
                [('type', '=', 'general')], limit=1)
            if not journal:
                raise UserError(_("No General journal found."))

        total_accumulated = sum(
            asset.depreciation_line_ids
            .filtered(lambda l: l.state == 'posted')
            .mapped('depreciation_value')
        )

        disposal_gain_loss_account = self.env['accounting.account'].search(
            [('code', '=', '420000')], limit=1)

        move_lines = []

        if total_accumulated > 0:
            move_lines.append((0, 0, {
                'account_id': asset.account_depreciation_id.id,
                'name': 'Disposal - Accumulated Depreciation',
                'debit': total_accumulated,
                'credit': 0.0,
            }))

        if self.sale_price > 0:
            cash_account = self.env['accounting.account'].search(
                [('type_id.code', 'in', ['bank', 'cash'])], limit=1)
            if cash_account:
                move_lines.append((0, 0, {
                    'account_id': cash_account.id,
                    'name': 'Disposal - Sale Proceeds',
                    'debit': self.sale_price,
                    'credit': 0.0,
                }))

        asset_value = asset.fair_value if asset.fair_value else asset.original_value
        move_lines.append((0, 0, {
            'account_id': asset.account_asset_id.id,
            'name': 'Disposal - Remove Asset',
            'debit': 0.0,
            'credit': asset_value,
        }))

        gain_loss = self.gain_loss
        if gain_loss != 0 and disposal_gain_loss_account:
            if gain_loss > 0:
                move_lines.append((0, 0, {
                    'account_id': disposal_gain_loss_account.id,
                    'name': 'Disposal - Gain on Disposal',
                    'debit': 0.0,
                    'credit': gain_loss,
                }))
            else:
                move_lines.append((0, 0, {
                    'account_id': disposal_gain_loss_account.id,
                    'name': 'Disposal - Loss on Disposal',
                    'debit': abs(gain_loss),
                    'credit': 0.0,
                }))

        if move_lines:
            move = self.env['accounting.move'].create({
                'ref': 'Disposal: %s' % (asset.asset_number or asset.name),
                'date': self.disposal_date,
                'journal_id': journal.id,
                'line_ids': move_lines,
            })
            if move.is_balanced:
                try:
                    move.action_post()
                except UserError:
                    pass
            asset.disposal_move_id = move.id

        asset.state = 'disposed'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asset Disposed'),
                'message': _(
                    'Asset %(name)s has been disposed. '
                    'Gain/Loss: %(gl)s'
                ) % {
                    'name': asset.name,
                    'gl': f"Rp {gain_loss:,.0f}",
                },
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
