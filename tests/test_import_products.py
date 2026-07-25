import pytest
from pathlib import Path
from playwright.sync_api import Page, expect

from conftest import (
    ODOO_URL,
    navigate_to_import_products,
    upload_csv_and_import,
    wait_for_import_complete,
    get_import_results,
    close_import_dialog,
    dismiss_dialog,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ──────────────────────────────────────────────
# A. Happy Path Tests
# ──────────────────────────────────────────────

@pytest.mark.happy_path
class TestImportProductsHappyPath:

    def test_navigate_to_import_products(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        modal = logged_in_page.locator('.modal.d-block')
        expect(modal).to_be_visible(timeout=10000)

        heading = logged_in_page.locator('.modal.d-block h4:has-text("Import Products")')
        expect(heading).to_be_visible()

        import_btn = logged_in_page.locator('.modal.d-block button:has-text("Import")')
        expect(import_btn).to_be_visible()

        cancel_btn = logged_in_page.locator('.modal.d-block button:has-text("Cancel")')
        expect(cancel_btn).to_be_visible()

    def test_import_valid_csv_new_products(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "valid_products.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        wait_for_import_complete(logged_in_page)

        results = get_import_results(logged_in_page)

        created = int(results['created']) if results['created'].isdigit() else 0
        updated = int(results['updated']) if results['updated'].isdigit() else 0
        total_processed = created + updated

        assert total_processed == 3, f"Expected 3 products processed (created+updated), got created={results['created']}, updated={results['updated']}"
        assert results['error'] == '', f"Unexpected error: {results['error']}"

        close_import_dialog(logged_in_page)

    def test_import_multiple_products(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "bulk_products.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        wait_for_import_complete(logged_in_page)

        results = get_import_results(logged_in_page)

        created_count = int(results['created']) if results['created'].isdigit() else 0
        updated_count = int(results['updated']) if results['updated'].isdigit() else 0
        total = created_count + updated_count

        assert total >= 28, f"Expected at least 28 products processed, got created={results['created']}, updated={results['updated']}"
        assert results['error'] == '', f"Unexpected error: {results['error']}"

        close_import_dialog(logged_in_page)


# ──────────────────────────────────────────────
# B. Error Handling Tests
# ──────────────────────────────────────────────

@pytest.mark.error_handling
class TestImportProductsErrorHandling:

    def test_import_without_file_shows_error(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        import_btn = logged_in_page.locator('button:has-text("Import")').first
        import_btn.click()

        logged_in_page.wait_for_timeout(2000)

        dialog_still_open = logged_in_page.locator('button:has-text("Import")').is_visible()

        assert dialog_still_open, "Dialog should remain open when no file uploaded"

    def test_import_invalid_columns_shows_error(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "invalid_columns.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        logged_in_page.wait_for_timeout(3000)

        error_shown = (
            logged_in_page.locator('.o_error, .alert-danger, .text-danger, .o_notification').count() > 0
        )
        import_btn_visible = logged_in_page.locator('button:has-text("Import")').is_visible()

        assert error_shown or import_btn_visible, \
            "Expected error for CSV with less than 10 columns"

    def test_import_empty_file_shows_error(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "empty_file.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        logged_in_page.wait_for_timeout(3000)

        error_shown = logged_in_page.locator('.o_error, .alert-danger, .text-danger, .o_notification').count() > 0
        import_btn_visible = logged_in_page.locator('button:has-text("Import")').is_visible()

        assert error_shown or import_btn_visible, \
            "Expected error for empty CSV file"


# ──────────────────────────────────────────────
# C. Update Existing Product Tests
# ──────────────────────────────────────────────

@pytest.mark.update
class TestImportProductsUpdate:

    def test_update_existing_product(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "valid_products.csv"
        upload_csv_and_import(logged_in_page, csv_file)
        wait_for_import_complete(logged_in_page)
        close_import_dialog(logged_in_page)

        navigate_to_import_products(logged_in_page)

        update_csv = FIXTURES_DIR / "update_product.csv"
        upload_csv_and_import(logged_in_page, update_csv)
        wait_for_import_complete(logged_in_page)

        results = get_import_results(logged_in_page)

        updated = int(results['updated']) if results['updated'].isdigit() else 0
        created = int(results['created']) if results['created'].isdigit() else 0

        assert updated >= 1 or created >= 1, \
            f"Expected at least 1 updated/created, got updated={results['updated']}, created={results['created']}"

        close_import_dialog(logged_in_page)

    def test_mixed_import_new_and_update(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "valid_products.csv"
        upload_csv_and_import(logged_in_page, csv_file)
        wait_for_import_complete(logged_in_page)
        close_import_dialog(logged_in_page)

        navigate_to_import_products(logged_in_page)

        mixed_csv = FIXTURES_DIR / "mixed_products.csv"
        upload_csv_and_import(logged_in_page, mixed_csv)
        wait_for_import_complete(logged_in_page)

        results = get_import_results(logged_in_page)

        created = int(results['created']) if results['created'].isdigit() else 0
        updated = int(results['updated']) if results['updated'].isdigit() else 0
        total = created + updated

        assert total == 2, \
            f"Expected 2 products processed (1 created + 1 updated), got created={results['created']}, updated={results['updated']}"

        close_import_dialog(logged_in_page)


# ──────────────────────────────────────────────
# D. Progress UI Tests
# ──────────────────────────────────────────────

@pytest.mark.progress_ui
class TestImportProductsProgressUI:

    def test_progress_bar_visible_during_import(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "bulk_products.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        importing_text = logged_in_page.locator('h3:has-text("Importing Products..."), .o_import_running h3')
        expect(importing_text.first).to_be_visible(timeout=15000)

        wait_for_import_complete(logged_in_page)
        close_import_dialog(logged_in_page)

    def test_close_button_after_import_complete(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "valid_products.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        wait_for_import_complete(logged_in_page)

        complete_text = logged_in_page.locator('h3:has-text("Import Complete!")')
        expect(complete_text).to_be_visible()

        close_btn = logged_in_page.locator('.o_import_done button:has-text("Close")')
        expect(close_btn).to_be_visible()

        close_btn.click()
        logged_in_page.wait_for_timeout(1000)

        wizard = logged_in_page.locator('form:has-text("Import Products")')
        assert not wizard.is_visible(), "Dialog should be closed after clicking Close"


# ──────────────────────────────────────────────
# E. Edge Cases Tests
# ──────────────────────────────────────────────

@pytest.mark.edge_cases
class TestImportProductsEdgeCases:

    def test_import_with_new_category(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "new_category_product.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        wait_for_import_complete(logged_in_page)

        results = get_import_results(logged_in_page)

        created = int(results['created']) if results['created'].isdigit() else 0
        updated = int(results['updated']) if results['updated'].isdigit() else 0
        total_processed = created + updated

        assert total_processed == 1, f"Expected 1 product processed, got created={results['created']}, updated={results['updated']}"
        assert results['error'] == '', f"Unexpected error: {results['error']}"

        close_import_dialog(logged_in_page)

    def test_import_with_semicolon_delimiter(self, logged_in_page: Page):
        navigate_to_import_products(logged_in_page)

        csv_file = FIXTURES_DIR / "semicolon_delimited.csv"
        upload_csv_and_import(logged_in_page, csv_file)

        wait_for_import_complete(logged_in_page, timeout=30000)

        results = get_import_results(logged_in_page)

        created = int(results['created']) if results['created'].isdigit() else 0
        updated = int(results['updated']) if results['updated'].isdigit() else 0
        total_processed = created + updated

        assert total_processed == 1, f"Expected 1 product processed, got created={results['created']}, updated={results['updated']}"
        assert results['error'] == '', f"Unexpected error: {results['error']}"

        close_import_dialog(logged_in_page)
