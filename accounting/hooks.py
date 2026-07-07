# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Ensure IDR currency exists and set it as the default for all records."""

    # 1. Find or create the IDR currency — handle duplicate gracefully
    idr = env['res.currency'].with_context(
        active_test=False
    ).search([('name', '=', 'IDR')], limit=1)

    if not idr:
        _logger.info("IDR currency not found — attempting to create it.")
        try:
            idr = env['res.currency'].create({
                'name': 'IDR',
                'full_name': 'Indonesian Rupiah',
                'symbol': 'Rp',
                'position': 'after',
                'rounding': 1.0,
                'active': True,
            })
            _logger.info("Created IDR currency (id=%s)", idr.id)
        except Exception as exc:
            _logger.warning(
                "Could not create IDR currency (%s). "
                "Trying to find existing record.", exc)
            # Another transaction may have created it — search again
            idr = env['res.currency'].with_context(
                active_test=False
            ).search([('name', '=', 'IDR')], limit=1)
            if not idr:
                _logger.error(
                    "IDR currency still not found after create attempt. "
                    "Aborting currency setup."
                )
                return
            _logger.info(
                "Found existing IDR currency after create conflict (id=%s)",
                idr.id)

    # Ensure the record is active
    if not idr.active:
        idr.write({'active': True})

    _logger.info("Using IDR currency: id=%s name=%s", idr.id, idr.name)

    # 2. Set company currency to IDR
    companies = env['res.company'].search([])
    for company in companies:
        try:
            company.write({'currency_id': idr.id})
        except Exception as exc:
            _logger.warning(
                "Could not set currency for company '%s': %s",
                company.name, exc)
    _logger.info("Set %s company(s) currency to IDR", len(companies))

    # 3. Set ALL chart of accounts to IDR
    try:
        accounts = env['accounting.account'].search([])
        if accounts:
            accounts.write({'currency_id': idr.id})
            _logger.info("Updated %s chart of accounts to IDR", len(accounts))
    except Exception as exc:
        _logger.warning("Could not update COA currency: %s", exc)

    # 4. Update all journal entries to IDR
    try:
        moves = env['accounting.move'].search([])
        if moves:
            moves.write({'currency_id': idr.id})
    except Exception as exc:
        _logger.warning("Could not update move currency: %s", exc)

    # 5. Update all bank statements to IDR
    try:
        statements = env['accounting.bank.statement'].search([])
        if statements:
            statements.write({'currency_id': idr.id})
    except Exception as exc:
        _logger.warning("Could not update statement currency: %s", exc)

    _logger.info("IDR currency setup complete.")
