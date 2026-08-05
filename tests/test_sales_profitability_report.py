import pytest
from playwright.sync_api import Page

from conftest import ODOO_URL

RPC_JS = """
async (params) => {
    async function rpcCall(model, method, args, kwargs) {
        const response = await fetch('/web/dataset/call_kw', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                params: {model, method, args: args || [], kwargs: kwargs || {}}})
        });
        const data = await response.json();
        if (data.error) {
            throw new Error(JSON.stringify(data.error));
        }
        return data.result;
    }

    const stamp = Date.now();
    const customerName = 'Profit Test Cus ' + stamp;
    const categoryName = 'Profit Test Cat ' + stamp;
    const productName = 'Profit Test Prod ' + stamp;

    // Resolve GL accounts by code (seeded in chart_of_accounts.xml)
    async function findAccount(code) {
        const res = await rpcCall('accounting.account', 'search_read', [[['code', '=', code]]], {fields: ['id'], limit: 1});
        return res.length ? res[0].id : null;
    }
    const incomeAcc = await findAccount('400000');
    const expenseAcc = await findAccount('500000');
    const stockAcc = await findAccount('113100');
    const arAcc = await findAccount('110000');
    if (!incomeAcc || !expenseAcc || !stockAcc || !arAcc) {
        return {error: 'Missing seed accounts: ' + JSON.stringify({incomeAcc, expenseAcc, stockAcc, arAcc})};
    }

    // Master data
    const custCatId = await rpcCall('sales.cust_category', 'create', [{
        category_name: 'Profit Test CC ' + stamp,
    }], {});
    const customerId = await rpcCall('sales.customer', 'create', [{
        customer_name: customerName,
        email: 'profit.' + stamp + '@test.local',
        cust_category: custCatId,
    }], {});

    const categoryId = await rpcCall('sales.product_category', 'create', [{
        category_name: categoryName,
        income_account_id: incomeAcc,
        expense_account_id: expenseAcc,
        stock_account_id: stockAcc,
    }], {});

    const productId = await rpcCall('sales.products', 'create', [{
        product_name: productName,
        product_category: categoryId,
        price: params.productCost,          // COGS unit cost
        base_price: params.productCost,     // sales price fallback
        price_yen: 0,
        stock: 100,
    }], {});

    // Helper builders
    async function buildOrder(customerId, productId, orderDate) {
        return rpcCall('sales.sales_order', 'create', [{
            customer_id: customerId,
            date_ordered: orderDate || null,
            order_line_ids: [[0, 0, {
                product_id: productId,
                quantity: params.qty,
                unit_price: params.unitPrice,
            }]],
        }], {});
    }
    async function buildInvoice(soId, customerId, productId, extra) {
        return rpcCall('sales.invoice', 'create', [Object.assign({
            sales_order_id: soId,
            customer_id: customerId,
            invoice_date: params.invoiceDate || null,
            line_ids: [[0, 0, {
                product_id: productId,
                description: productName,
                quantity: params.qty,
                unit_price: params.unitPrice,
            }]],
        }, extra || {})], {});
    }
    async function buildDelivery(soId, customerId, productId) {
        return rpcCall('sales.delivery', 'create', [{
            sales_order_id: soId,
            customer_id: customerId,
            delivery_date: params.deliveryDate || null,
            line_ids: [[0, 0, {
                product_id: productId,
                description: productName,
                quantity: params.qty,
            }]],
        }], {});
    }
    async function buildFund(stamp) {
        return rpcCall('accounting.petty.cash', 'create', [{
            code: 'PC' + stamp,
            name: 'Profit Test Fund ' + stamp,
            journal_id: await findJournal('cash'),
            default_cash_account_id: await findAccount('100500'),
        }], {});
    }
    async function findJournal(jtype) {
        const res = await rpcCall('accounting.journal', 'search_read', [[['type', '=', jtype]]], {fields: ['id'], limit: 1});
        return res.length ? res[0].id : null;
    }
    async function buildExpense(fundId, categoryId, soId, amount, tagged) {
        return rpcCall('accounting.petty.cash.expense', 'create', [{
            fund_id: fundId,
            description: 'Profit Test Expense ' + stamp,
            sales_order_id: tagged ? soId : false,
            line_ids: [[0, 0, {
                category_id: categoryId,
                description: 'Profit test line',
                amount: amount,
            }]],
        }], {});
    }

    const expCategoryId = await rpcCall('accounting.petty.cash.category', 'create', [{
        name: 'Profit Test PC Cat ' + stamp,
        expense_account_id: expenseAcc,
    }], {});

    const fundId = await buildFund(stamp);
    const soId = await buildOrder(customerId, productId);
    const so = await rpcCall('sales.sales_order', 'read', [soId, ['sales_code']], {});
    const salesCode = so[0].sales_code;

    // Tagged supporting expense: posted (only when a positive amount is given)
    let expenseId = null;
    if (params.supportingAmount > 0) {
        const expId = await buildExpense(fundId, expCategoryId, soId, params.supportingAmount, true);
        await rpcCall('accounting.petty.cash.expense', 'action_post', [[expId]], {});
        expenseId = expId;
    }

    return {
        stamp: stamp,
        customerId: customerId,
        soId: soId,
        salesCode: salesCode,
        expenseId: expenseId,
        productId: productId,
        error: null,
    };
}
"""


def _run_rpc(page: Page, params: dict):
    result = page.evaluate(RPC_JS, params)
    assert result and not result.get('error'), f"Setup failed: {result}"
    return result


def _get_report_rows(page: Page, sales_code: str):
    return page.evaluate("""async (salesCode) => {
        async function rpcCall(model, method, args, kwargs) {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                    params: {model, method, args: args || [], kwargs: kwargs || {}}})
            });
            const data = await response.json();
            if (data.error) { throw new Error(JSON.stringify(data.error)); }
            return data.result;
        }
        const rows = await rpcCall('accounting.sales_profitability_report', 'search_read',
            [[['sale_order_name', '=', salesCode]]],
            {fields: ['id', 'sale_order_name', 'sale_order_date', 'customer_id',
                      'total_revenue', 'cost_cogs', 'cost_commission', 'cost_supporting',
                      'total_cost', 'margin_amount', 'margin_percent', 'has_transaction', 'currency_id']});
        return rows;
    }""", sales_code)


@pytest.mark.profitability
class TestProfitabilityReportData:

    def test_happy_path_margin_values(self, logged_in_page: Page):
        """Revenue - COGS - supporting = margin, with correct margin %."""
        params = {
            'qty': 2,
            'unitPrice': 1000,
            'productCost': 400,
            'supportingAmount': 150,
            'invoiceDate': None,
            'deliveryDate': None,
        }
        setup = _run_rpc(logged_in_page, params)

        result = logged_in_page.evaluate("""async (p) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                        params: {model, method, args: args || [], kwargs: kwargs || {}}})
                });
                const data = await response.json();
                if (data.error) { throw new Error(JSON.stringify(data.error)); }
                return data.result;
            }
            const stamp = p.stamp;
            const customerName = 'Profit Test Cus ' + stamp;
            const customer = await rpcCall('sales.customer', 'search_read', [[['customer_name', '=', customerName]]], {fields: ['id'], limit: 1});
            const productName = 'Profit Test Prod ' + stamp;
            const product = await rpcCall('sales.products', 'search_read', [[['product_name', '=', productName]]], {fields: ['id'], limit: 1});

            const so = await rpcCall('sales.sales_order', 'search_read', [[['customer_id', '=', customer[0].id]]], {fields: ['id', 'sales_code'], limit: 1});
            const soId = so[0].id;

            const invoice = await rpcCall('sales.invoice', 'create', [{
                sales_order_id: soId,
                customer_id: customer[0].id,
                invoice_date: '2026-08-02',
                line_ids: [[0, 0, {
                    product_id: product[0].id,
                    description: productName,
                    quantity: p.qty,
                    unit_price: p.unitPrice,
                }]],
            }], {});
            await rpcCall('sales.invoice', 'action_post', [[invoice]], {});

            const delivery = await rpcCall('sales.delivery', 'create', [{
                sales_order_id: soId,
                customer_id: customer[0].id,
                delivery_date: '2026-08-02',
                line_ids: [[0, 0, {
                    product_id: product[0].id,
                    description: productName,
                    quantity: p.qty,
                }]],
            }], {});
            await rpcCall('sales.delivery', 'action_done', [[delivery]], {});

            // Untagged expense must NOT count toward cost_supporting
            const expense = await rpcCall('accounting.petty.cash.expense', 'create', [{
                fund_id: await (async () => {
                    const res = await rpcCall('accounting.petty.cash', 'search_read', [[['name', '=', 'Profit Test Fund ' + stamp]]], {fields: ['id'], limit: 1});
                    return res[0].id;
                })(),
                description: 'Profit Test Untagged ' + stamp,
                sales_order_id: false,
                line_ids: [[0, 0, {
                    category_id: await (async () => {
                        const res = await rpcCall('accounting.petty.cash.category', 'search_read', [[['name', '=', 'Profit Test PC Cat ' + stamp]]], {fields: ['id'], limit: 1});
                        return res[0].id;
                    })(),
                    description: 'untagged',
                    amount: 9999,
                }]],
            }], {});
            await rpcCall('accounting.petty.cash.expense', 'action_post', [[expense]], {});

            return {salesCode: so[0].sales_code};
        }""", {'qty': params['qty'], 'unitPrice': params['unitPrice'], 'stamp': setup['stamp']})

        rows = _get_report_rows(logged_in_page, setup['salesCode'])
        assert rows, f"No report row for {setup['salesCode']}"
        row = rows[0]
        assert row['total_revenue'] == 2000, f"revenue={row['total_revenue']}"
        assert row['cost_cogs'] == 800, f"cogs={row['cost_cogs']}"
        assert row['cost_commission'] == 0, f"commission={row['cost_commission']}"
        assert row['cost_supporting'] == 150, f"supporting={row['cost_supporting']}"
        assert row['total_cost'] == 950, f"total_cost={row['total_cost']}"
        assert row['margin_amount'] == 1050, f"margin={row['margin_amount']}"
        assert abs(row['margin_percent'] - 52.5) < 0.01, f"margin_percent={row['margin_percent']}"
        assert row['has_transaction'] is True, f"has_transaction={row['has_transaction']}"

    def test_draft_invoice_not_counted(self, logged_in_page: Page):
        """SO whose invoice stays in draft reports zero revenue and no transaction."""
        params = {
            'qty': 1,
            'unitPrice': 500,
            'productCost': 300,
            'supportingAmount': 0,
            'invoiceDate': None,
            'deliveryDate': None,
        }
        setup = _run_rpc(logged_in_page, params)
        result = logged_in_page.evaluate("""async (p) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                        params: {model, method, args: args || [], kwargs: kwargs || {}}})
                });
                const data = await response.json();
                if (data.error) { throw new Error(JSON.stringify(data.error)); }
                return data.result;
            }
            const customer = await rpcCall('sales.customer', 'search_read', [[['customer_name', '=', 'Profit Test Cus ' + p.stamp]]], {fields: ['id'], limit: 1});
            const product = await rpcCall('sales.products', 'search_read', [[['product_name', '=', 'Profit Test Prod ' + p.stamp]]], {fields: ['id'], limit: 1});
            const so = await rpcCall('sales.sales_order', 'search_read', [[['customer_id', '=', customer[0].id]]], {fields: ['id', 'sales_code'], limit: 1});
            const invoice = await rpcCall('sales.invoice', 'create', [{
                sales_order_id: so[0].id,
                customer_id: customer[0].id,
                invoice_date: '2026-08-02',
                line_ids: [[0, 0, {
                    product_id: product[0].id,
                    description: 'draft invoice line',
                    quantity: p.qty,
                    unit_price: p.unitPrice,
                }]],
            }], {});
            return {salesCode: so[0].sales_code, invoiceId: invoice};
        }""", {'qty': params['qty'], 'unitPrice': params['unitPrice'], 'stamp': setup['stamp']})

        rows = _get_report_rows(logged_in_page, result['salesCode'])
        assert rows, f"No report row for {result['salesCode']}"
        row = rows[0]
        assert row['total_revenue'] == 0, f"revenue={row['total_revenue']}"
        assert row['cost_cogs'] == 0, f"cogs={row['cost_cogs']}"
        assert row['has_transaction'] is False, f"has_transaction={row['has_transaction']}"

    def test_commission_included(self, logged_in_page: Page):
        """Invoice with a salesperson triggers commission cost on the report."""
        params = {
            'qty': 4,
            'unitPrice': 1000,
            'productCost': 600,
            'supportingAmount': 0,
            'invoiceDate': None,
            'deliveryDate': None,
        }
        setup = _run_rpc(logged_in_page, params)
        result = logged_in_page.evaluate("""async (p) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                        params: {model, method, args: args || [], kwargs: kwargs || {}}})
                });
                const data = await response.json();
                if (data.error) { throw new Error(JSON.stringify(data.error)); }
                return data.result;
            }
            // Ensure a commission plan exists (5% of untaxed)
            const plans = await rpcCall('accounting.commission.plan', 'search_read', [[['name', '=', 'Profit Test Plan ' + p.stamp]]], {fields: ['id'], limit: 1});
            if (!plans.length) {
                const expenseAcc = await rpcCall('accounting.account', 'search_read', [[['code', '=', '510000']]], {fields: ['id'], limit: 1});
                const payableAcc = await rpcCall('accounting.account', 'search_read', [[['code', '=', '220000']]], {fields: ['id'], limit: 1});
                const journal = await rpcCall('accounting.journal', 'search_read', [[['type', '=', 'general']]], {fields: ['id'], limit: 1});
                await rpcCall('accounting.commission.plan', 'create', [{
                    name: 'Profit Test Plan ' + p.stamp,
                    type: 'percentage',
                    rate: 5,
                    based_on: 'untaxed',
                    journal_id: journal.length ? journal[0].id : false,
                    expense_account_id: expenseAcc.length ? expenseAcc[0].id : false,
                    payable_account_id: payableAcc.length ? payableAcc[0].id : false,
                }], {});
            }
            // A salesperson (custom user) to attach to the invoice
            const users = await rpcCall('general.custom_users', 'search_read', [[]], {fields: ['id'], limit: 1});
            if (!users.length) { return {error: 'No custom user found'}; }
            const sp = users[0].id;

            const customer = await rpcCall('sales.customer', 'search_read', [[['customer_name', '=', 'Profit Test Cus ' + p.stamp]]], {fields: ['id'], limit: 1});
            const product = await rpcCall('sales.products', 'search_read', [[['product_name', '=', 'Profit Test Prod ' + p.stamp]]], {fields: ['id'], limit: 1});
            const so = await rpcCall('sales.sales_order', 'search_read', [[['customer_id', '=', customer[0].id]]], {fields: ['id', 'sales_code'], limit: 1});

            const invoice = await rpcCall('sales.invoice', 'create', [{
                sales_order_id: so[0].id,
                customer_id: customer[0].id,
                invoice_date: '2026-08-02',
                sales_name: sp,
                line_ids: [[0, 0, {
                    product_id: product[0].id,
                    description: 'commission invoice line',
                    quantity: p.qty,
                    unit_price: p.unitPrice,
                }]],
            }], {});
            await rpcCall('sales.invoice', 'action_post', [[invoice]], {});

            const delivery = await rpcCall('sales.delivery', 'create', [{
                sales_order_id: so[0].id,
                customer_id: customer[0].id,
                delivery_date: '2026-08-02',
                line_ids: [[0, 0, {
                    product_id: product[0].id,
                    description: 'commission delivery line',
                    quantity: p.qty,
                }]],
            }], {});
            await rpcCall('sales.delivery', 'action_done', [[delivery]], {});

            // The plan actually applied is the first active plan (limit=1 in code)
            const applied = await rpcCall('accounting.commission.plan', 'search_read',
                [[['active', '=', true]]], {fields: ['id', 'name', 'type', 'rate', 'based_on'], limit: 1});

            return {salesCode: so[0].sales_code, applied: applied.length ? applied[0] : null};
        }""", {'qty': params['qty'], 'unitPrice': params['unitPrice'], 'stamp': setup['stamp']})

        if result and result.get('error'):
            pytest.skip(result['error'])

        rows = _get_report_rows(logged_in_page, result['salesCode'])
        assert rows, f"No report row for {result['salesCode']}"
        row = rows[0]
        assert row['total_revenue'] == 4000, f"revenue={row['total_revenue']}"
        assert row['cost_cogs'] == 2400, f"cogs={row['cost_cogs']}"

        # Compute expected commission from the plan actually applied
        plan = result.get('applied')
        if not plan:
            assert row['cost_commission'] == 0, f"commission={row['cost_commission']}"
            expected_commission = 0.0
        else:
            rate = plan['rate']
            commission_amount = (4000 * rate / 100.0) if plan['type'] == 'percentage' else rate
            assert row['cost_commission'] == commission_amount, \
                f"commission={row['cost_commission']} expected={commission_amount} (plan {plan['name']})"
            expected_commission = commission_amount

        expected_cost = 2400 + expected_commission
        expected_margin = 4000 - expected_cost
        assert row['total_cost'] == expected_cost, f"total_cost={row['total_cost']} expected={expected_cost}"
        assert row['margin_amount'] == expected_margin, f"margin={row['margin_amount']} expected={expected_margin}"
        assert abs(row['margin_percent'] - (expected_margin / 4000 * 100.0)) < 0.01, \
            f"margin_percent={row['margin_percent']}"

    def test_wizard_domain_filtering(self, logged_in_page: Page):
        """Wizard returns a working domain filtered by customer / dates / SO."""
        params = {
            'qty': 1,
            'unitPrice': 100,
            'productCost': 50,
            'supportingAmount': 0,
            'invoiceDate': None,
            'deliveryDate': None,
        }
        setup = _run_rpc(logged_in_page, params)
        result = logged_in_page.evaluate("""async (p) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                        params: {model, method, args: args || [], kwargs: kwargs || {}}})
                });
                const data = await response.json();
                if (data.error) { throw new Error(JSON.stringify(data.error)); }
                return data.result;
            }
            const wizardId = await rpcCall('accounting.sales_profitability_report.wizard', 'create', [{
                date_from: '2026-08-01',
                date_to: '2026-08-31',
                customer_id: p.customerId,
            }], {});
            const generate = await rpcCall('accounting.sales_profitability_report.wizard', 'action_generate', [[wizardId]], {});
            const domain = generate.domain;
            const rows = await rpcCall('accounting.sales_profitability_report', 'search_read',
                [domain], {fields: ['sale_order_name', 'customer_id'], limit: 20});
            return {domain: domain, resModel: generate.res_model, rows: rows};
        }""", {'customerId': setup['customerId']})

        assert ['customer_id', '=', setup['customerId']] in result['domain'], f"domain={result['domain']}"
        assert ['sale_order_date', '>=', '2026-08-01'] in result['domain'], f"domain={result['domain']}"
        assert ['sale_order_date', '<=', '2026-08-31'] in result['domain'], f"domain={result['domain']}"
        assert result['resModel'] == 'accounting.sales_profitability_report', \
            f"res_model={result['resModel']}"
        assert any(r['customer_id'][0] == setup['customerId'] for r in result['rows']), \
            f"Expected filtered rows for customer {setup['customerId']}, got {result['rows']}"

    def test_cancelled_delivery_not_counted(self, logged_in_page: Page):
        """A cancelled (never done) delivery contributes no COGS."""
        params = {
            'qty': 3,
            'unitPrice': 700,
            'productCost': 200,
            'supportingAmount': 0,
            'invoiceDate': None,
            'deliveryDate': None,
        }
        setup = _run_rpc(logged_in_page, params)
        result = logged_in_page.evaluate("""async (p) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                        params: {model, method, args: args || [], kwargs: kwargs || {}}})
                });
                const data = await response.json();
                if (data.error) { throw new Error(JSON.stringify(data.error)); }
                return data.result;
            }
            const customer = await rpcCall('sales.customer', 'search_read', [[['customer_name', '=', 'Profit Test Cus ' + p.stamp]]], {fields: ['id'], limit: 1});
            const product = await rpcCall('sales.products', 'search_read', [[['product_name', '=', 'Profit Test Prod ' + p.stamp]]], {fields: ['id'], limit: 1});
            const so = await rpcCall('sales.sales_order', 'search_read', [[['customer_id', '=', customer[0].id]]], {fields: ['id', 'sales_code'], limit: 1});
            const soId = so[0].id;

            const invoice = await rpcCall('sales.invoice', 'create', [{
                sales_order_id: soId,
                customer_id: customer[0].id,
                invoice_date: '2026-08-02',
                line_ids: [[0, 0, {
                    product_id: product[0].id,
                    description: 'cancel delivery invoice line',
                    quantity: p.qty,
                    unit_price: p.unitPrice,
                }]],
            }], {});
            await rpcCall('sales.invoice', 'action_post', [[invoice]], {});

            // Delivery created then cancelled BEFORE done -> no COGS move
            const delivery = await rpcCall('sales.delivery', 'create', [{
                sales_order_id: soId,
                customer_id: customer[0].id,
                delivery_date: '2026-08-02',
                line_ids: [[0, 0, {
                    product_id: product[0].id,
                    description: 'cancel delivery line',
                    quantity: p.qty,
                }]],
            }], {});
            await rpcCall('sales.delivery', 'action_cancel', [[delivery]], {});

            return {salesCode: so[0].sales_code};
        }""", {'qty': params['qty'], 'unitPrice': params['unitPrice'], 'stamp': setup['stamp']})

        rows = _get_report_rows(logged_in_page, result['salesCode'])
        assert rows, f"No report row for {result['salesCode']}"
        row = rows[0]
        assert row['total_revenue'] == 2100, f"revenue={row['total_revenue']}"
        assert row['cost_cogs'] == 0, f"cogs={row['cost_cogs']}"
        assert row['cost_supporting'] == 0, f"supporting={row['cost_supporting']}"


@pytest.mark.profitability
class TestProfitabilityServiceBill:

    def test_service_bill_cost_in_supporting(self, logged_in_page: Page):
        """PRD §8: Posted Service Bill tagged to SO via PO.sales_order_id
        appears in cost_supporting of the profitability report."""
        params = {
            'qty': 1,
            'unitPrice': 200000,
            'productCost': 0,
            'supportingAmount': 0,
        }
        setup = _run_rpc(logged_in_page, params)

        result = logged_in_page.evaluate("""async (p) => {
            async function rpcCall(model, method, args, kwargs) {
                const response = await fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': odoo.csrf_token || ''},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', id: Math.floor(Math.random() * 100000),
                        params: {model, method, args: args || [], kwargs: kwargs || {}}})
                });
                const data = await response.json();
                if (data.error) { throw new Error(JSON.stringify(data.error)); }
                return data.result;
            }

            // Resolve expense account
            const expenseRes = await rpcCall('accounting.account', 'search_read',
                [[['code', '=', '530000']]], {fields: ['id'], limit: 1});
            if (!expenseRes.length) return {error: 'Missing expense account 530000'};
            const expenseAcc = expenseRes[0].id;

            // Create vendor
            const vendorId = await rpcCall('purchases.vendor', 'create', [{
                vendor_name: 'Profit Test SVC Vendor ' + p.stamp,
            }], {});

            // Create service category
            const svcCatId = await rpcCall('purchases.service_category', 'create', [{
                category_name: 'Profit Test SVC Cat ' + p.stamp,
                expense_account_id: expenseAcc,
            }], {});

            // Find the SO created in setup
            const customer = await rpcCall('sales.customer', 'search_read',
                [[['customer_name', '=', 'Profit Test Cus ' + p.stamp]]],
                {fields: ['id'], limit: 1});
            const so = await rpcCall('sales.sales_order', 'search_read',
                [[['customer_id', '=', customer[0].id]]],
                {fields: ['id', 'sales_code'], limit: 1});
            const soId = so[0].id;

            // Create Service PO tagged to SO
            const poId = await rpcCall('purchases.purchase_order', 'create', [{
                order_type: 'service',
                vendor_id: vendorId,
                sales_order_id: soId,
                order_line_ids: [[0, 0, {
                    service_category_id: svcCatId,
                    description: 'Profit Test Service Line',
                    quantity: 1,
                    unit_price: p.unitPrice,
                }]],
            }], {skip_purchase_order_create_auth_check: true});

            // Confirm PO
            await rpcCall('purchases.purchase_order', 'action_confirm_order', [[poId]]);

            // Create Bill
            const billAction = await rpcCall('purchases.purchase_order', 'action_create_bill', [[poId]]);
            const billId = billAction.res_id;

            // Post Bill
            await rpcCall('purchases.bill', 'action_post', [[billId]]);

            return {salesCode: so[0].sales_code, unitPrice: p.unitPrice};
        }""", {'qty': params['qty'], 'unitPrice': params['unitPrice'], 'stamp': setup['stamp']})

        assert not result.get('error'), f"Setup failed: {result}"

        rows = _get_report_rows(logged_in_page, result['salesCode'])
        assert rows, f"No report row for {result['salesCode']}"
        row = rows[0]
        # Service bill expense should appear in cost_supporting
        assert row['cost_supporting'] == result['unitPrice'], \
            f"cost_supporting={row['cost_supporting']} expected={result['unitPrice']}"
        # total_cost should include the service bill cost
        assert row['total_cost'] >= result['unitPrice'], \
            f"total_cost={row['total_cost']} should include service bill cost"


@pytest.mark.profitability
@pytest.mark.smoke
class TestProfitabilityReportUI:

    def test_report_tree_view_renders(self, logged_in_page: Page):
        """Running the wizard's Tampilkan button opens the report tree with columns."""
        logged_in_page.goto(
            f"{ODOO_URL}/web#action=accounting.action_sales_profitability_wizard")
        logged_in_page.wait_for_load_state("domcontentloaded")
        logged_in_page.wait_for_timeout(5000)

        # Click Tampilkan (object button in the wizard footer)
        btn = logged_in_page.locator('button:has-text("Tampilkan"), .o_dialog button:has-text("Tampilkan")')
        assert btn.count() > 0, "Tampilkan button not found in wizard"
        btn.first.click()
        logged_in_page.wait_for_timeout(6000)

        # The report tree should render with the profitability columns
        rev_col = logged_in_page.locator('th:has-text("Total Revenue"), th:has-text("Revenue")')
        assert rev_col.count() > 0, "Revenue column not found in report tree"
        margin_col = logged_in_page.locator('th:has-text("Margin"), th:has-text("Margin (")')
        assert margin_col.count() > 0, "Margin column not found in report tree"

    def test_wizard_action_opens(self, logged_in_page: Page):
        """Opening the wizard from the menu shows the wizard form."""
        logged_in_page.goto(
            f"{ODOO_URL}/web#action=accounting.action_sales_profitability_wizard")
        logged_in_page.wait_for_load_state("domcontentloaded")
        logged_in_page.wait_for_timeout(5000)

        # Wizard form should render with the date filter fields
        date_from = logged_in_page.locator('.o_field_widget[name="date_from"] input')
        assert date_from.count() > 0, "date_from field not found in wizard"
