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


# =============================================================================
# Asset Management Helpers
# =============================================================================

def click_nav_item(page: Page, name: str):
    """Click a navbar item by text (handles both leaf <a> and dropdown <button>)"""
    sections = page.locator('.o_menu_sections')
    leaf = sections.locator(f'> a.o_nav_entry:has-text("{name}")')
    if leaf.count() > 0:
        leaf.first.click()
        page.wait_for_timeout(3000)
        return
    dropdown = sections.locator(f'button.dropdown-toggle:has-text("{name}")')
    if dropdown.count() > 0:
        dropdown.first.click()
        page.wait_for_timeout(2000)


def navigate_to_assets(page: Page):
    """Navigate to Accounting > Assets"""
    click_nav_item(page, "Accounting")
    page.wait_for_timeout(2000)
    # Assets is a leaf section under Accounting
    assets_link = page.locator('a.o_nav_entry:has-text("Assets"), a:has-text("Assets")')
    if assets_link.count() > 0:
        assets_link.first.click()
        page.wait_for_timeout(3000)


def navigate_to_asset_models(page: Page):
    """Navigate to Accounting > Accounting Configuration > Asset Models"""
    click_nav_item(page, "Accounting")
    page.wait_for_timeout(2000)
    # Click Configuration dropdown
    config_btn = page.locator('button.dropdown-toggle:has-text("Configuration")')
    if config_btn.count() > 0:
        config_btn.first.click()
        page.wait_for_timeout(2000)
    # Click Asset Models
    asset_models_link = page.locator('a.dropdown-item:has-text("Asset Models")')
    if asset_models_link.count() > 0:
        asset_models_link.first.click()
        page.wait_for_timeout(3000)


def fill_field(page: Page, field_name: str, value: str, timeout: int = 5000):
    """Fill an Odoo form field by its field name (works with navigation.mixin and standard forms).
    
    Odoo 17 renders fields as: <div name="FIELD_NAME" class="o_field_widget"><input class="o_input" ...></div>
    So the <input> itself does NOT have name="FIELD_NAME" — we target the parent div.
    """
    # Strategy 1: Odoo field widget pattern - div[name] > input
    field_div = page.locator(f'.o_field_widget[name="{field_name}"] input, .o_field_widget[name="{field_name}"] textarea').first
    if field_div.count() == 0 or not field_div.is_visible(timeout=timeout):
        # Strategy 2: Direct input id
        field_div = page.locator(f'input#{field_name}_0, textarea#{field_name}_0').first
    if field_div.count() == 0 or not field_div.is_visible(timeout=timeout):
        # Strategy 3: Fallback to input[name]
        field_div = page.locator(f'input[name="{field_name}"], textarea[name="{field_name}"]').first
    field_div.wait_for(state="visible", timeout=timeout)
    field_div.click()
    field_div.fill(value)
    page.wait_for_timeout(500)


def select_field(page: Page, field_name: str, value: str, timeout: int = 5000):
    """Select an option in an Odoo selection field.
    
    Odoo 17 encodes option values as JSON strings (e.g. &quot;straight_line&quot;),
    so we try multiple strategies: exact value, JSON-encoded value, and label text.
    """
    sel = page.locator(f'.o_field_widget[name="{field_name}"] select, select#{field_name}_0').first
    if sel.count() == 0:
        sel = page.locator(f'select[name="{field_name}"]').first
    sel.wait_for(state="visible", timeout=timeout)
    # Try exact value first
    try:
        sel.select_option(value=value, timeout=3000)
        page.wait_for_timeout(500)
        return
    except Exception:
        pass
    # Try JSON-encoded value (Odoo wraps in quotes)
    try:
        sel.select_option(value=f'"{value}"', timeout=3000)
        page.wait_for_timeout(500)
        return
    except Exception:
        pass
    # Try by label text
    try:
        sel.select_option(label=value, timeout=3000)
        page.wait_for_timeout(500)
    except Exception:
        pass


def navigate_to_asset_model_new(page: Page):
    """Navigate directly to a new Asset Model form via action URL"""
    page.goto(f"{ODOO_URL}/web#model=assets.model&action=assets.action_asset_model&view_type=form")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(5000)


def navigate_to_asset_model_list(page: Page):
    """Navigate to Asset Models list view via action URL"""
    page.goto(f"{ODOO_URL}/web#model=assets.model&action=assets.action_asset_model&view_type=list")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(5000)


def navigate_to_asset_new(page: Page):
    """Navigate directly to a new Asset form via action URL"""
    page.goto(f"{ODOO_URL}/web#model=assets.asset&action=assets.action_asset_list&view_type=form")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(5000)


def navigate_to_asset_list(page: Page):
    """Navigate to Assets list view via action URL"""
    page.goto(f"{ODOO_URL}/web#model=assets.asset&action=assets.action_asset_list&view_type=list")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(5000)


def navigate_to_journal_entries(page: Page):
    """Navigate to Accounting > Journal Entries"""
    click_nav_item(page, "Accounting")
    page.wait_for_timeout(2000)
    je_link = page.locator('a.o_nav_entry:has-text("Journal Entries"), a:has-text("Journal Entries")')
    if je_link.count() > 0:
        je_link.first.click()
        page.wait_for_timeout(3000)


def click_new_button(page: Page):
    """Click the New button to create a new record"""
    # Try standard Odoo list view "New" button
    new_btn = page.locator('button.o_list_button_add:has-text("New"), button:has-text("New")')
    if new_btn.count() > 0:
        new_btn.first.click()
        page.wait_for_timeout(2000)
        return
    # Try link-style "New" button
    new_link = page.locator('a:has-text("New"), span:has-text("New")')
    if new_link.count() > 0:
        new_link.first.click()
        page.wait_for_timeout(2000)
        return
    raise Exception("New button not found")


def click_save_button(page: Page):
    """Click the Save button"""
    save_btn = page.locator('button:has-text("Save")')
    if save_btn.count() > 0:
        save_btn.first.click()
        page.wait_for_timeout(3000)
    else:
        raise Exception("Save button not found")


def click_edit_button(page: Page):
    """Click the Edit button"""
    edit_btn = page.locator('button:has-text("Edit")')
    if edit_btn.count() > 0:
        edit_btn.first.click()
        page.wait_for_timeout(2000)
    else:
        raise Exception("Edit button not found")


def click_header_button(page: Page, button_text: str):
    """Click a navigation.mixin header action button by text.
    
    Excludes statusbar radio buttons and disabled (pe-none) buttons.
    Uses button[name] or specific string match within the header statusbar_buttons area.
    """
    # Strategy 1: button with matching name attribute inside statusbar_buttons
    btn = page.locator(f'.o_statusbar_buttons button:has-text("{button_text}"):not([disabled]):not(.pe-none):not(.opacity-50)')
    if btn.count() > 0 and btn.first.is_visible(timeout=3000):
        btn.first.click()
        page.wait_for_timeout(3000)
        return
    # Strategy 2: any header button (not in statusbar)
    btn = page.locator(f'header button:has-text("{button_text}"):not([disabled]):not(.pe-none):not(.opacity-50):not([role="radio"])')
    if btn.count() > 0 and btn.first.is_visible(timeout=3000):
        btn.first.click()
        page.wait_for_timeout(3000)
        return
    raise Exception(f"Header button '{button_text}' not found or not visible")


def fill_dialog_field(page: Page, field_name: str, value: str, timeout: int = 5000):
    """Fill a field inside an Odoo dialog/wizard.
    
    After filling date fields, dismisses any open popover (date picker) by pressing Escape.
    Uses .modal selectors because .o_dialog has height=0 in Odoo 17.
    """
    for selector in [
        f'.modal .o_field_widget[name="{field_name}"] input',
        f'.modal input[id*="{field_name}"]',
        f'.o_dialog .o_field_widget[name="{field_name}"] input',
        f'.o_dialog input[id*="{field_name}"]',
    ]:
        inp = page.locator(selector).first
        if inp.count() > 0 and inp.is_visible(timeout=timeout):
            inp.click(force=True)
            inp.fill(value)
            page.wait_for_timeout(500)
            # Only dismiss popover if one is actually visible (e.g. date picker)
            popover = page.locator('.o_popover:visible, .popover:visible, .o-datepicker:visible')
            if popover.count() > 0:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            return
    # Fallback: generic dialog input
    inp = page.locator('.modal input.o_input, .o_dialog input.o_input').first
    if inp.count() > 0:
        inp.click(force=True)
        inp.fill(value)
        page.wait_for_timeout(500)
        popover = page.locator('.o_popover:visible, .popover:visible, .o-datepicker:visible')
        if popover.count() > 0:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)


def click_dialog_confirm(page: Page):
    """Click confirm in a dialog, handling both the button and the 'Are you sure?' popup.
    
    Uses .modal selectors because .o_dialog has height=0 in Odoo 17.
    """
    # First find the wizard's primary confirm button (e.g. "Confirm Disposal", "Confirm Revaluation")
    # Exclude .o-default-button which is the hidden Ok in the wizard itself
    confirm_btn = page.locator('.modal .modal-footer button.btn-primary:not(.o-default-button):visible')
    if confirm_btn.count() > 0:
        confirm_btn.first.click()
        page.wait_for_timeout(2000)
    else:
        # Fallback: any primary visible button in modal footer
        confirm_btn = page.locator('.modal .btn-primary:visible')
        if confirm_btn.count() > 0:
            confirm_btn.first.click()
            page.wait_for_timeout(2000)
    
    # Handle "Are you sure?" confirmation popup (the Ok button from Odoo's Dialog.confirm)
    ok_btn = page.locator('.modal .btn-primary:has-text("Ok"):visible, .modal .btn-primary:has-text("OK"):visible')
    if ok_btn.count() > 0:
        ok_btn.first.click()
    page.wait_for_timeout(3000)


def open_first_record(page: Page):
    """Click on the first record in a list/tree view"""
    row = page.locator('table tbody tr, .o_list_view tbody tr').first
    row.click()
    page.wait_for_timeout(3000)


def fill_many2one_field(page: Page, field_name: str, search_text: str, timeout: int = 10000):
    """Fill an Odoo Many2one field by typing search text and selecting first result."""
    inp = page.locator(f'.o_field_widget[name="{field_name}"] input.o-autocomplete--input')
    if inp.count() == 0:
        inp = page.locator(f'.o_field_widget[name="{field_name}"] input.o_input')
    inp.wait_for(state="visible", timeout=timeout)
    inp.click()
    page.wait_for_timeout(300)
    inp.fill("")
    page.wait_for_timeout(200)
    inp.type(search_text, delay=50)
    page.wait_for_timeout(3000)

    # Strategy 1: click first visible dropdown item
    for selector in [
        f'.o-autocomplete .dropdown-item',
        f'.o-autocomplete li',
        f'.o-autocomplete [role="option"]',
        f'.o-dropdown-menu li',
    ]:
        items = page.locator(selector)
        if items.count() > 0:
            for i in range(min(items.count(), 5)):
                if items.nth(i).is_visible():
                    items.nth(i).click()
                    page.wait_for_timeout(1000)
                    return

    # Strategy 2: keyboard navigation
    inp.press("ArrowDown")
    page.wait_for_timeout(500)
    inp.press("Enter")
    page.wait_for_timeout(1000)


def create_asset_with_accounts(page: Page, name: str, confirm: bool = False):
    """Create an asset via JSON-RPC, then navigate to it."""
    result = page.evaluate("""async (params) => {
        const {name, confirm} = params;
        
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

        // Find accounts and journal
        const accResults = await rpcCall('accounting.account', 'name_search', ['113200'], {limit: 1});
        const depResults = await rpcCall('accounting.account', 'name_search', ['113100'], {limit: 1});
        const expResults = await rpcCall('accounting.account', 'name_search', ['611'], {limit: 1});
        const jrnlResults = await rpcCall('accounting.journal', 'name_search', ['Miscellaneous'], {limit: 1});

        // Find revaluation accounts (surplus and loss) - try common codes
        const surplusResults = await rpcCall('accounting.account', 'name_search', ['420'], {limit: 1});
        const lossResults = await rpcCall('accounting.account', 'name_search', ['612'], {limit: 1});
        // Fallback to expense account if specific codes don't exist
        const surplusAccountId = surplusResults?.[0]?.[0] || expResults?.[0]?.[0];
        const lossAccountId = lossResults?.[0]?.[0] || expResults?.[0]?.[0];

        const assetAccountId = accResults?.[0]?.[0];
        const depAccountId = depResults?.[0]?.[0] || assetAccountId;
        const expAccountId = expResults?.[0]?.[0] || assetAccountId;
        const journalId = jrnlResults?.[0]?.[0];

        if (!assetAccountId || !journalId) {
            const allAccs = await rpcCall('accounting.account', 'name_search', [''], {limit: 5});
            const allJrnls = await rpcCall('accounting.journal', 'name_search', [''], {limit: 5});
            return {error: 'Missing: asset=' + !!assetAccountId + ', jrnl=' + !!journalId + ', allAccs=' + JSON.stringify(allAccs) + ', allJrnls=' + JSON.stringify(allJrnls)};
        }

        const assetId = await rpcCall('assets.asset', 'create', [{
            name: name,
            acquisition_date: '2026-01-15',
            original_value: 15000000,
            method_number: 60,
            account_asset_id: assetAccountId,
            account_depreciation_id: depAccountId,
            account_depreciation_expense_id: expAccountId,
            journal_id: journalId,
            account_revaluation_surplus_id: surplusAccountId,
            account_revaluation_loss_id: lossAccountId,
        }], {});

        if (confirm) {
            await rpcCall('assets.asset', 'action_confirm', [[assetId]], {});
        }

        return {id: assetId};
    }""", {"name": name, "confirm": confirm})

    if result and result.get('error'):
        raise Exception(f"Failed to create asset: {result['error']}")
    if result and result.get('id'):
        page.goto(f"{ODOO_URL}/web#model=assets.asset&id={result['id']}&view_type=form")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)


def get_state_text(page: Page) -> str:
    """Get the current state from a navigation.mixin statusbar widget.
    
    Odoo statusbar renders as radio buttons with data-value attribute.
    The current state is the one with aria-current="step".
    """
    # Strategy 1: statusbar radio button with aria-current="step"
    current = page.locator('.o_statusbar_buttons button[aria-current="step"], .o_field_widget[name="state"] button[aria-current="step"]')
    if current.count() > 0 and current.first.is_visible(timeout=3000):
        return current.first.get_attribute("data-value", timeout=3000).strip().lower()
    # Strategy 2: hidden input (standard widget)
    state_input = page.locator('input[name="state"], select[name="state"]')
    if state_input.count() > 0:
        return state_input.first.input_value().strip().lower()
    # Strategy 3: checked radio button with data-value
    checked = page.locator('button[data-value][aria-checked="true"]')
    if checked.count() > 0:
        return checked.first.get_attribute("data-value").strip().lower()
    return ''
