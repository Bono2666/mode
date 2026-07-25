import os
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

# Configuration
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8017")
ODOO_DB = os.getenv("ODOO_DB", "mina")
ODOO_USER = os.getenv("ODOO_USER", "trihambono@gmail.com")
ODOO_PASS = os.getenv("ODOO_PASS", "Tr1-B0n0")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def context(browser: Browser):
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    yield ctx
    ctx.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    pg = context.new_page()
    yield pg
    pg.close()


@pytest.fixture(scope="function")
def logged_in_page(page: Page) -> Page:
    login(page)
    return page


def login(page: Page):
    page.goto(f"{ODOO_URL}/web/login?db={ODOO_DB}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)

    page.fill('input[name="login"]', ODOO_USER)
    page.fill('input[name="password"]', ODOO_PASS)

    page.click('button[type="submit"]')
    page.wait_for_timeout(8000)


def navigate_to_import_products(page: Page):
    page.locator('span:text-is("Sales")').first.click()
    page.wait_for_timeout(3000)

    page.locator(':text("Import Products")').first.click()
    page.wait_for_timeout(5000)


def upload_csv_and_import(page: Page, csv_path: Path):
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(str(csv_path))
    page.wait_for_timeout(500)

    import_btn = page.locator('button:has-text("Import")').first
    import_btn.click()


def wait_for_import_complete(page: Page, timeout: int = 60000):
    page.wait_for_selector(
        '.o_import_done, .o_import_error, h3:has-text("Import Complete!"), h3:has-text("Import Error")',
        timeout=timeout
    )


def get_import_results(page: Page) -> dict:
    results = {'created': '0', 'updated': '0', 'skipped': '0', 'error': ''}

    try:
        el = page.locator('.o_import_done p:has-text("Created:") strong, .o_import_error p:has-text("Created:") strong')
        if el.count() > 0:
            results['created'] = el.first.inner_text(timeout=3000)
    except Exception:
        pass

    try:
        el = page.locator('.o_import_done p:has-text("Updated:") strong, .o_import_error p:has-text("Updated:") strong')
        if el.count() > 0:
            results['updated'] = el.first.inner_text(timeout=3000)
    except Exception:
        pass

    try:
        el = page.locator('.o_import_done p:has-text("Skipped:") strong, .o_import_error p:has-text("Skipped:") strong')
        if el.count() > 0:
            results['skipped'] = el.first.inner_text(timeout=3000)
    except Exception:
        pass

    try:
        el = page.locator('.o_import_done .text-danger, .o_import_error .text-danger')
        if el.count() > 0:
            results['error'] = el.first.inner_text(timeout=3000)
    except Exception:
        pass

    return results


def close_import_dialog(page: Page):
    close_btn = page.locator(
        '.o_import_done button:has-text("Close"), .o_import_error button:has-text("Close")'
    )
    if close_btn.count() > 0:
        close_btn.click()
        page.wait_for_timeout(1000)
    else:
        cancel_btn = page.locator('.o_dialog button:has-text("Cancel")')
        if cancel_btn.count() > 0:
            cancel_btn.first.click()
            page.wait_for_timeout(1000)


def dismiss_dialog(page: Page):
    cancel_btn = page.locator('.o_dialog button:has-text("Cancel")')
    if cancel_btn.count() > 0:
        cancel_btn.first.click()
        page.wait_for_timeout(500)
