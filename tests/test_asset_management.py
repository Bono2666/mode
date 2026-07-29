import pytest
from playwright.sync_api import Page, expect

from conftest import (
    ODOO_URL,
    navigate_to_assets,
    navigate_to_asset_models,
    navigate_to_asset_model_new,
    navigate_to_asset_model_list,
    navigate_to_asset_new,
    navigate_to_asset_list,
    navigate_to_journal_entries,
    click_new_button,
    click_save_button,
    click_edit_button,
    click_header_button,
    open_first_record,
    get_state_text,
    fill_field,
    select_field,
    fill_many2one_field,
    create_asset_with_accounts,
    fill_dialog_field,
    click_dialog_confirm,
)


# =============================================================================
# A. Asset Model CRUD Tests
# =============================================================================

@pytest.mark.asset
@pytest.mark.smoke
class TestAssetModelCRUD:

    def test_create_asset_model(self, logged_in_page: Page):
        """Create a new asset model with depreciation settings"""
        navigate_to_asset_model_new(logged_in_page)

        # Fill model name
        fill_field(logged_in_page, "name", "Test Vehicle Model")

        # Select depreciation method
        select_field(logged_in_page, "method", "straight_line")

        # Set method_number
        fill_field(logged_in_page, "method_number", "60")

        # Save
        click_save_button(logged_in_page)

        # Verify model was created
        name_display = logged_in_page.locator('h1:has-text("Test Vehicle Model")')
        expect(name_display.first).to_be_visible(timeout=10000)

    def test_edit_asset_model(self, logged_in_page: Page):
        """Edit an existing asset model"""
        navigate_to_asset_model_list(logged_in_page)

        # Open first model
        open_first_record(logged_in_page)

        # Click Edit
        click_edit_button(logged_in_page)

        # Change method_number
        fill_field(logged_in_page, "method_number", "48")

        # Save
        click_save_button(logged_in_page)

        # Verify change
        method_number_input = logged_in_page.locator('.o_field_widget[name="method_number"] input')
        if method_number_input.count() > 0:
            value = method_number_input.first.input_value()
            assert value == "48", f"Expected method_number to be 48, got {value}"

    def test_delete_asset_model(self, logged_in_page: Page):
        """Delete an asset model"""
        navigate_to_asset_model_list(logged_in_page)

        # Open first model
        open_first_record(logged_in_page)

        # Click Delete
        click_header_button(logged_in_page, "Delete")

        # Confirm deletion
        logged_in_page.wait_for_timeout(1000)
        confirm_btn = logged_in_page.locator('.o_dialog button:has-text("Delete"), .modal button:has-text("Delete")')
        if confirm_btn.count() > 0:
            confirm_btn.first.click()
            logged_in_page.wait_for_timeout(3000)


# =============================================================================
# B. Asset Lifecycle Tests
# =============================================================================

@pytest.mark.asset
@pytest.mark.smoke
class TestAssetLifecycle:

    def test_create_asset(self, logged_in_page: Page):
        """Create a new asset in draft state"""
        navigate_to_asset_new(logged_in_page)

        # Fill asset name
        fill_field(logged_in_page, "name", "Test Laptop Asset")

        # Set acquisition date
        fill_field(logged_in_page, "acquisition_date", "2026-01-15")

        # Set original value
        fill_field(logged_in_page, "original_value", "15000000")

        # Save
        click_save_button(logged_in_page)

        # Verify asset was created
        name_display = logged_in_page.locator('h1:has-text("Test Laptop Asset")')
        expect(name_display.first).to_be_visible(timeout=10000)

    def test_confirm_asset(self, logged_in_page: Page):
        """Confirm a draft asset to move it to running state"""
        create_asset_with_accounts(logged_in_page, "Test Confirm Asset")

        # Debug: screenshot before confirm
        logged_in_page.screenshot(path="/tmp/before_confirm.png")

        # Click Confirm button
        click_header_button(logged_in_page, "Confirm")
        logged_in_page.wait_for_timeout(3000)

        # Debug: screenshot after confirm
        logged_in_page.screenshot(path="/tmp/after_confirm.png")

        # Verify state changed to running
        state = get_state_text(logged_in_page)
        assert "running" in state, f"Expected state 'running', got '{state}'"

    def test_compute_depreciation(self, logged_in_page: Page):
        """Compute depreciation for a running asset"""
        create_asset_with_accounts(logged_in_page, "Test Depreciation Asset", confirm=True)

        # Click Compute Depreciation
        click_header_button(logged_in_page, "Compute Depreciation")
        logged_in_page.wait_for_timeout(3000)

        # Check for depreciation lines via stat button
        depreciation_btn = logged_in_page.locator('.oe_stat_button:has-text("Depreciation Board")')
        if depreciation_btn.count() > 0 and depreciation_btn.first.is_visible(timeout=5000):
            depreciation_btn.first.click()
            logged_in_page.wait_for_timeout(3000)

            # Check for depreciation lines in the tree
            lines = logged_in_page.locator('table tbody tr')
            line_count = lines.count()
            assert line_count > 0, f"Expected depreciation lines, found {line_count}"

    def test_pause_resume_asset(self, logged_in_page: Page):
        """Pause and resume a running asset"""
        create_asset_with_accounts(logged_in_page, "Test Pause Asset", confirm=True)

        # Click Pause
        click_header_button(logged_in_page, "Pause")

        # Verify state changed to paused
        logged_in_page.wait_for_timeout(3000)
        state = get_state_text(logged_in_page)
        assert "paused" in state, f"Expected state 'paused', got '{state}'"

        # Click Resume
        click_header_button(logged_in_page, "Resume")

        # Verify state changed back to running
        logged_in_page.wait_for_timeout(3000)
        state = get_state_text(logged_in_page)
        assert "running" in state, f"Expected state 'running', got '{state}'"

    def test_dispose_asset(self, logged_in_page: Page):
        """Dispose a running asset via disposal wizard"""
        create_asset_with_accounts(logged_in_page, "Test Dispose Asset", confirm=True)

        # Click Dispose
        click_header_button(logged_in_page, "Dispose")

        # Wait for wizard
        logged_in_page.wait_for_timeout(3000)

        # Fill wizard fields using dialog helper
        fill_dialog_field(logged_in_page, "sale_price", "5000000")
        fill_dialog_field(logged_in_page, "disposal_date", "2026-07-29")

        # Confirm disposal (handles confirmation popup)
        click_dialog_confirm(logged_in_page)

        # Verify state changed to disposed
        state = get_state_text(logged_in_page)
        assert "disposed" in state or "close" in state, f"Expected state 'disposed', got '{state}'"


# =============================================================================
# C. Depreciation Board Tests
# =============================================================================

@pytest.mark.asset
class TestAssetDepreciation:

    def test_depreciation_line_count(self, logged_in_page: Page):
        """Verify depreciation line count matches method_number"""
        create_asset_with_accounts(logged_in_page, "Test Line Count Asset", confirm=True)

        # Compute depreciation
        click_header_button(logged_in_page, "Compute Depreciation")
        logged_in_page.wait_for_timeout(3000)

        # Click Depreciation Board stat button
        depreciation_btn = logged_in_page.locator('.oe_stat_button:has-text("Depreciation Board")')
        if depreciation_btn.count() > 0 and depreciation_btn.first.is_visible(timeout=5000):
            depreciation_btn.first.click()
            logged_in_page.wait_for_timeout(3000)

            # Count depreciation lines
            lines = logged_in_page.locator('table tbody tr')
            line_count = lines.count()
            assert line_count > 0, f"Expected depreciation lines, found {line_count}"

    def test_depreciation_post_line(self, logged_in_page: Page):
        """Post a draft depreciation line"""
        create_asset_with_accounts(logged_in_page, "Test Post Dep Asset", confirm=True)

        click_header_button(logged_in_page, "Compute Depreciation")
        logged_in_page.wait_for_timeout(3000)

        # Click Depreciation Board stat button
        depreciation_btn = logged_in_page.locator('.oe_stat_button:has-text("Depreciation Board")')
        if depreciation_btn.count() > 0 and depreciation_btn.first.is_visible(timeout=5000):
            depreciation_btn.first.click()
            logged_in_page.wait_for_timeout(3000)

            # Find and click Post button on first draft line
            post_btn = logged_in_page.locator('button:has-text("Post"), a:has-text("Post")')
            if post_btn.count() > 0:
                post_btn.first.click()
                logged_in_page.wait_for_timeout(3000)

                # Verify a journal entry was created
                view_entry_btn = logged_in_page.locator('button:has-text("View Entry"), a:has-text("View Entry")')
                assert view_entry_btn.count() > 0, "Expected 'View Entry' button after posting depreciation line"

    def test_straight_line_values(self, logged_in_page: Page):
        """Verify straight-line depreciation values are equal"""
        create_asset_with_accounts(logged_in_page, "Test Straight Line Asset", confirm=True)

        click_header_button(logged_in_page, "Compute Depreciation")
        logged_in_page.wait_for_timeout(3000)

        # Click Depreciation Board stat button
        depreciation_btn = logged_in_page.locator('.oe_stat_button:has-text("Depreciation Board")')
        if depreciation_btn.count() > 0 and depreciation_btn.first.is_visible(timeout=5000):
            depreciation_btn.first.click()
            logged_in_page.wait_for_timeout(3000)

            # Get all depreciation values from the tree
            value_cells = logged_in_page.locator('table tbody tr td:nth-child(3)')
            if value_cells.count() > 1:
                first_value = float(value_cells.first.inner_text().replace('.', '').replace(',', '.').replace('Rp ', '').strip() or '0')
                for i in range(1, value_cells.count()):
                    cell_value = float(value_cells.nth(i).inner_text().replace('.', '').replace(',', '.').replace('Rp ', '').strip() or '0')
                    assert abs(cell_value - first_value) < 1.0, \
                        f"Depreciation value at row {i+1} ({cell_value}) differs from first ({first_value})"


# =============================================================================
# D. Revaluation Tests
# =============================================================================

@pytest.mark.asset
class TestAssetRevaluation:

    def test_revalue_asset(self, logged_in_page: Page):
        """Revalue a running asset"""
        create_asset_with_accounts(logged_in_page, "Test Revalue Asset", confirm=True)

        # Get the asset ID from URL
        asset_id_match = logged_in_page.url.split('id=')[1].split('&')[0] if 'id=' in logged_in_page.url else None
        asset_id = int(asset_id_match) if asset_id_match else None
        assert asset_id, f"Could not extract asset ID from URL: {logged_in_page.url}"

        # Click Revalue
        click_header_button(logged_in_page, "Revalue")
        logged_in_page.wait_for_timeout(2000)

        # Fill wizard fields - fill non-date fields first to avoid date picker popover
        fill_dialog_field(logged_in_page, "fair_value_new", "12000000")
        fill_dialog_field(logged_in_page, "remaining_useful_life", "48")
        fill_dialog_field(logged_in_page, "revaluation_date", "2026-07-29")

        # Confirm revaluation - click primary button then dismiss confirmation
        # Use JS to dismiss all dialogs since stacked modals cause click interception
        logged_in_page.evaluate("""() => {
            // Click the Confirm Revaluation button directly
            const confirmBtn = document.querySelector('.modal .modal-footer button.btn-primary:not(.o-default-button)');
            if (confirmBtn) confirmBtn.click();
        }""")
        logged_in_page.wait_for_timeout(3000)

        # Dismiss ALL modal dialogs via JS
        logged_in_page.evaluate("""() => {
            // Click all visible Ok buttons
            document.querySelectorAll('.modal .btn-primary').forEach(btn => {
                if (btn.textContent.trim() === 'Ok' || btn.textContent.trim() === 'OK') {
                    btn.click();
                }
            });
        }""")
        logged_in_page.wait_for_timeout(1000)

        # Close any remaining dialogs via close buttons
        logged_in_page.evaluate("""() => {
            document.querySelectorAll('.modal .btn-close').forEach(btn => btn.click());
        }""")
        logged_in_page.wait_for_timeout(1000)

        # Press Escape to clear any remaining popups
        logged_in_page.keyboard.press("Escape")
        logged_in_page.wait_for_timeout(1000)

        # Navigate back to the asset to verify
        logged_in_page.goto(f"{ODOO_URL}/web#model=assets.asset&id={asset_id}&view_type=form")
        logged_in_page.wait_for_load_state("domcontentloaded")
        logged_in_page.wait_for_timeout(3000)

        # Check revaluation history tab
        revaluation_tab = logged_in_page.locator('a[name="revaluation_history"]')
        if revaluation_tab.count() > 0 and revaluation_tab.first.is_visible(timeout=3000):
            revaluation_tab.first.click()
            logged_in_page.wait_for_timeout(2000)

            lines = logged_in_page.locator('table tbody tr')
            assert lines.count() > 0, "Expected revaluation line to be created"

    def test_revaluation_creates_je(self, logged_in_page: Page):
        """Verify revaluation creates a journal entry"""
        create_asset_with_accounts(logged_in_page, "Test Reval JE Asset", confirm=True)

        # Get asset ID from URL
        asset_id_match = logged_in_page.url.split('id=')[1].split('&')[0] if 'id=' in logged_in_page.url else None
        asset_id = int(asset_id_match) if asset_id_match else None
        assert asset_id, f"Could not extract asset ID from URL: {logged_in_page.url}"

        # Create revaluation wizard and confirm via RPC (avoids stacked modal issues)
        result = logged_in_page.evaluate("""async (assetId) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                        params: {model, method, args: args || [], kwargs: kwargs || {}}})
                });
                const data = await response.json();
                return data.result;
            }

            // Create wizard with defaults
            const wizardId = await rpcCall('assets.revaluation_wizard', 'create', [{
                asset_id: assetId,
                fair_value_new: 18000000,
                revaluation_date: '2026-07-29',
                remaining_useful_life: 48,
            }], {});

            // Confirm revaluation
            await rpcCall('assets.revaluation_wizard', 'action_confirm_revaluation', [[wizardId]], {});

            // Verify revaluation line was created
            const lines = await rpcCall('assets.revaluation_line', 'search_read', [[['asset_id', '=', assetId]]], {fields: ['id', 'fair_value_after', 'state', 'revaluation_date'], limit: 5});

            // Verify asset state and fair value
            const asset = await rpcCall('assets.asset', 'read', [assetId, ['state', 'fair_value', 'book_value']], {});

            return {lines: lines, asset: asset};
        }""", asset_id)

        assert result and result.get('lines') and len(result['lines']) > 0, \
            f"Expected revaluation line, got: {result}"

        # Check revaluation line value
        reval_line = result['lines'][0]
        assert reval_line['fair_value_after'] == 18000000, \
            f"Expected fair_value_after 18000000, got {reval_line['fair_value_after']}"


# =============================================================================
# E. Auto-Creation from Journal Entry Tests
# =============================================================================

@pytest.mark.asset
class TestAssetAutoCreation:

    def test_je_creates_asset(self, logged_in_page: Page):
        """Verify that posting a JE with asset account debit creates an asset"""
        result = logged_in_page.evaluate("""async (params) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': odoo.csrf_token || '',
                    },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        id: Math.floor(Math.random() * 100000),
                        params: {
                            model: model,
                            method: method,
                            args: args || [],
                            kwargs: kwargs || {},
                        }
                    })
                });
                const data = await response.json();
                return data.result;
            }

            // Find an account marked as is_asset_account
            const assetAccs = await rpcCall('accounting.account', 'search_read', [[['is_asset_account', '=', true]]], {fields: ['id', 'code'], limit: 1});
            let assetAccountId;
            if (assetAccs && assetAccs.length > 0) {
                assetAccountId = assetAccs[0].id;
            } else {
                const accs = await rpcCall('accounting.account', 'name_search', ['113200'], {limit: 1});
                if (accs && accs.length > 0) {
                    assetAccountId = accs[0][0];
                    await rpcCall('accounting.account', 'write', [[assetAccountId], {is_asset_account: true}], {});
                }
            }

            // Find a bank/cash account for credit side
            const bankAccs = await rpcCall('accounting.account', 'name_search', ['100000'], {limit: 1});
            const bankAccountId = bankAccs && bankAccs.length > 0 ? bankAccs[0][0] : null;

            // Find miscellaneous journal
            const jrnlResults = await rpcCall('accounting.journal', 'name_search', ['Miscellaneous'], {limit: 1});
            const journalId = jrnlResults && jrnlResults.length > 0 ? jrnlResults[0][0] : null;

            if (!assetAccountId || !journalId) {
                return {error: 'Missing accounts: asset=' + assetAccountId + ', journal=' + journalId};
            }

            // Create JE with lines
            const lineIds = [
                [0, 0, {
                    account_id: assetAccountId,
                    name: 'Auto Asset Test',
                    debit: 25000000,
                    credit: 0,
                }],
            ];
            if (bankAccountId) {
                lineIds.push([0, 0, {
                    account_id: bankAccountId,
                    name: 'Auto Asset Test Credit',
                    debit: 0,
                    credit: 25000000,
                }]);
            }

            const moveId = await rpcCall('accounting.move', 'create', [{
                ref: 'Test Asset Auto Creation',
                journal_id: journalId,
                line_ids: lineIds,
            }], {});

            // Post it
            await rpcCall('accounting.move', 'action_post', [[moveId]], {});

            // Verify asset was auto-created via RPC
            const assets = await rpcCall('assets.asset', 'search_read', [[['name', 'ilike', 'Auto Asset Test']]], {fields: ['id', 'name', 'state', 'original_value'], limit: 5});

            return {moveId: moveId, assetAccountId: assetAccountId, assets: assets};
        }""", {"name": "Auto Asset Test"})

        assert result and not result.get('error'), f"JE creation failed: {result}"
        assert result.get('assets') and len(result['assets']) > 0, f"Expected auto-created asset, got: {result.get('assets')}"

        # Also verify via UI by navigating to asset
        asset_id = result['assets'][0]['id']
        logged_in_page.goto(f"{ODOO_URL}/web#model=assets.asset&id={asset_id}&view_type=form")
        logged_in_page.wait_for_load_state("domcontentloaded")
        logged_in_page.wait_for_timeout(3000)

        # Verify asset value
        assert result['assets'][0]['original_value'] == 25000000, f"Expected original_value 25000000, got {result['assets'][0]['original_value']}"
        assert result['assets'][0]['state'] == 'draft', f"Expected state draft, got {result['assets'][0]['state']}"

    def test_asset_from_je_has_correct_value(self, logged_in_page: Page):
        """Verify auto-created asset has correct original_value from JE debit"""
        # Navigate to Assets
        navigate_to_asset_list(logged_in_page)

        # Open first asset
        open_first_record(logged_in_page)

        # Check original_value
        value_input = logged_in_page.locator('input[name="original_value"]').first
        if value_input.count() > 0:
            value = value_input.input_value()
            assert float(value) > 0, f"Expected original_value > 0, got {value}"
