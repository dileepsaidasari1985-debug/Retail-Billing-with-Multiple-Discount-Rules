"""
Automated Unit & Integration Tests (Python unittest)
Smart Retail Billing and Discount Management System (Case Study #7)
"""

import csv
import io
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from billing_logic import (
    DEFAULT_DISCOUNT_RULES,
    apply_maximum_concession,
    calculate_cash_change,
    calculate_invoice,
    calculate_line_subtotal,
    calculate_threshold_discount,
    generate_invoice_number,
    get_next_discount_nudge,
    validate_product_data,
    validate_quantity,
)
from database import (
    add_product,
    create_invoice_from_cart,
    delete_product,
    get_dashboard_and_report_stats,
    get_invoice_by_id,
    get_product_by_id,
    get_products,
    get_tax_rules,
    init_db,
    load_sample_data,
    update_product,
)


class BillingLogicTests(unittest.TestCase):
    """Unit tests for core Python billing, discount, concession, and tax calculations."""

    def test_single_product_subtotal(self):
        self.assertEqual(calculate_line_subtotal(540.0, 3), 1620.00)
        self.assertEqual(calculate_line_subtotal(199.95, 2), 399.90)

    def test_negative_price_or_quantity_rejected(self):
        with self.assertRaises(ValueError):
            calculate_line_subtotal(-10.0, 2)
        with self.assertRaises(ValueError):
            calculate_line_subtotal(100.0, -1)

    def test_threshold_discount_boundaries(self):
        # Below ₹1,000 -> 0%
        self.assertEqual(calculate_threshold_discount(0, DEFAULT_DISCOUNT_RULES), (0.0, 0.0))
        self.assertEqual(calculate_threshold_discount(999.99, DEFAULT_DISCOUNT_RULES), (0.0, 0.0))

        # ₹1,000 - ₹2,499 -> 5%
        self.assertEqual(calculate_threshold_discount(1000.00, DEFAULT_DISCOUNT_RULES), (5.0, 50.0))
        self.assertEqual(calculate_threshold_discount(2499.99, DEFAULT_DISCOUNT_RULES), (5.0, 125.0))

        # ₹2,500 - ₹4,999 -> 10%
        self.assertEqual(calculate_threshold_discount(2500.00, DEFAULT_DISCOUNT_RULES), (10.0, 250.0))
        self.assertEqual(calculate_threshold_discount(4999.00, DEFAULT_DISCOUNT_RULES), (10.0, 499.90))

        # ₹5,000 and above -> 15%
        self.assertEqual(calculate_threshold_discount(5000.00, DEFAULT_DISCOUNT_RULES), (15.0, 750.0))
        self.assertEqual(calculate_threshold_discount(8000.00, DEFAULT_DISCOUNT_RULES), (15.0, 1200.0))

    def test_maximum_concession_enforcement(self):
        final_disc, capped = apply_maximum_concession(1200.0, 1000.0)
        self.assertEqual(final_disc, 1000.0)
        self.assertTrue(capped)

        final_disc_ok, capped_ok = apply_maximum_concession(750.0, 1000.0)
        self.assertEqual(final_disc_ok, 750.0)
        self.assertFalse(capped_ok)

    def test_multiple_products_category_taxes_and_concession_cap(self):
        # Electronics (18% tax): 2 * 3000 = 6000
        # Grocery (5% tax): 2 * 1000 = 2000
        # Subtotal = 8000 -> 15% threshold = 1200 -> Capped at 1000!
        # Proportional discount: Electronics gets 750, Grocery gets 250
        # Taxable: Electronics 5250 -> tax 945.00; Grocery 1750 -> tax 87.50
        # Total tax = 1032.50; Final Payable = 8000 - 1000 + 1032.50 = 8032.50
        cart = [
            {
                "product_id": 1,
                "product_code": "ELE-901",
                "product_name": "Smart Speaker",
                "category": "Electronics",
                "unit_price": 3000.00,
                "quantity": 2,
                "discount_eligible": True,
            },
            {
                "product_id": 2,
                "product_code": "GRO-901",
                "product_name": "Olive Oil Pack",
                "category": "Grocery",
                "unit_price": 1000.00,
                "quantity": 2,
                "discount_eligible": True,
            },
        ]
        tax_map = {"Electronics": 18.0, "Grocery": 5.0}
        bill = calculate_invoice(cart, tax_map, DEFAULT_DISCOUNT_RULES, 1000.0)

        self.assertEqual(bill["purchase_subtotal"], 8000.00)
        self.assertEqual(bill["discount_percent"], 15.0)
        self.assertEqual(bill["eligible_discount"], 1200.00)
        self.assertEqual(bill["final_discount"], 1000.00)
        self.assertTrue(bill["concession_capped"])
        self.assertEqual(bill["taxable_amount"], 7000.00)
        self.assertEqual(bill["total_tax"], 1032.50)
        self.assertEqual(bill["final_payable"], 8032.50)
        self.assertEqual(len(bill["nested_line_items"]), 2)
        self.assertIn("FINAL PAYABLE (INR):", bill["receipt_pattern"])

    def test_non_discountable_product_excluded_from_discount(self):
        cart = [
            {
                "product_id": 1,
                "product_code": "STA-403",
                "product_name": "Calculator",
                "category": "Stationery",
                "unit_price": 1500.00,
                "quantity": 1,
                "discount_eligible": False,
            }
        ]
        bill = calculate_invoice(cart, {"Stationery": 5.0}, DEFAULT_DISCOUNT_RULES, 1000.0)
        self.assertEqual(bill["eligible_subtotal"], 0.0)
        self.assertEqual(bill["final_discount"], 0.0)
        self.assertEqual(bill["total_tax"], 75.00)
        self.assertEqual(bill["final_payable"], 1575.00)

    def test_quantity_and_product_validation(self):
        ok_qty, _, parsed = validate_quantity("3", 5)
        self.assertTrue(ok_qty)
        self.assertEqual(parsed, 3)

        bad_zero, _, _ = validate_quantity("0", 5)
        self.assertFalse(bad_zero)

        bad_over, msg, _ = validate_quantity("6", 5)
        self.assertFalse(bad_over)
        self.assertIn("exceeds available stock", msg)

        ok_prod, errs, _ = validate_product_data("Tea", "GRO-777", "Grocery", "-10", "-2")
        self.assertFalse(ok_prod)
        self.assertGreaterEqual(len(errs), 2)

    def test_invoice_number_format(self):
        inv_num = generate_invoice_number(7, "2026-11-25")
        self.assertEqual(inv_num, "INV-20261125-0007")


class DatabaseAndWebIntegrationTests(unittest.TestCase):
    """Integration tests for SQLite persistence, Flask routes, cart workflow, and CSV export."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_retail.db")
        init_db(self.db_path, seed_if_empty=True)
        self.app = create_app(db_path=self.db_path, seed_if_empty=True)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _extract_csrf(self, html_text):
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_text)
        self.assertIsNotNone(match, "CSRF token should be present in form HTML")
        return match.group(1)

    def test_sample_products_and_duplicate_code_prevention(self):
        products = get_products(self.db_path)
        self.assertGreaterEqual(len(products), 15)

        # Idempotent sample loading must not duplicate
        added_prods, added_invs = load_sample_data(self.db_path, include_invoices=True)
        self.assertEqual(added_prods, 0)
        self.assertEqual(added_invs, 0)

        # Duplicate product code blocked
        ok, msg, _ = add_product(self.db_path, "GRO-101", "Duplicate Rice", "Grocery", 500.0, 10)
        self.assertFalse(ok)
        self.assertIn("already exists", msg)

    def test_invoice_snapshot_preserved_when_product_price_changes(self):
        ok, _, pid = add_product(self.db_path, "TST-999", "Test Blender", "Household", 2000.00, 10, True)
        self.assertTrue(ok)

        success, _, inv_id = create_invoice_from_cart(self.db_path, {pid: 2}, "Meera")
        self.assertTrue(success)
        inv_before = get_invoice_by_id(self.db_path, inv_id)
        original_total = inv_before["invoice"]["final_payable"]

        # Stock should have decreased from 10 to 8
        updated_prod = get_product_by_id(self.db_path, pid)
        self.assertEqual(updated_prod["available_stock"], 8)

        # Now change product price and delete product; historical invoice must remain identical
        update_product(self.db_path, pid, "TST-999", "Test Blender", "Household", 3500.00, 8, True)
        delete_product(self.db_path, pid)

        inv_after = get_invoice_by_id(self.db_path, inv_id)
        self.assertEqual(inv_after["invoice"]["final_payable"], original_total)
        self.assertEqual(inv_after["items"][0]["unit_price"], 2000.00)

    def test_end_to_end_billing_checkout_and_csv_exports(self):
        # 1. Dashboard loads real SQLite metrics
        dash_resp = self.client.get("/")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b"Smart Retail Billing Dashboard", dash_resp.data)

        # 2. Load billing counter & extract CSRF
        billing_resp = self.client.get("/billing")
        self.assertEqual(billing_resp.status_code, 200)
        html = billing_resp.get_data(as_text=True)
        csrf = self._extract_csrf(html)

        # Find a product in DB
        products = get_products(self.db_path)
        target = products[0]

        # 3. Add product to cart
        add_resp = self.client.post(
            "/billing/cart/add",
            data={"csrf_token": csrf, "product_id": str(target["id"]), "quantity": "2"},
            follow_redirects=True,
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertIn(target["product_name"].encode("utf-8"), add_resp.data)

        # 4. Extract checkout nonce and submit checkout
        billing_html = add_resp.get_data(as_text=True)
        nonce_match = re.search(r'name="checkout_nonce"\s+value="([^"]+)"', billing_html)
        self.assertIsNotNone(nonce_match)
        nonce = nonce_match.group(1)

        checkout_resp = self.client.post(
            "/billing/checkout",
            data={"csrf_token": csrf, "checkout_nonce": nonce, "customer_name": "Karan Mehta"},
            follow_redirects=True,
        )
        self.assertEqual(checkout_resp.status_code, 200)
        self.assertIn(b"Karan Mehta", checkout_resp.data)
        self.assertIn(b"TAX INVOICE", checkout_resp.data)

        # 5. Re-submitting same nonce must NOT create duplicate invoice
        stats_before = get_dashboard_and_report_stats(self.db_path)["total_invoices"]
        dup_resp = self.client.post(
            "/billing/checkout",
            data={"csrf_token": csrf, "checkout_nonce": nonce, "customer_name": "Karan Mehta"},
            follow_redirects=True,
        )
        self.assertEqual(dup_resp.status_code, 200)
        stats_after = get_dashboard_and_report_stats(self.db_path)["total_invoices"]
        self.assertEqual(stats_before, stats_after)

        # 6. Verify invoice CSV download
        inv_csv_resp = self.client.get("/invoice/1/csv")
        self.assertEqual(inv_csv_resp.status_code, 200)
        self.assertIn("text/csv", inv_csv_resp.content_type)
        parsed_csv = list(csv.reader(io.StringIO(inv_csv_resp.get_data(as_text=True))))
        self.assertTrue(any("Invoice Number" in row for row in parsed_csv))

        # 7. Verify reports page and full report CSV download
        rep_resp = self.client.get("/reports")
        self.assertEqual(rep_resp.status_code, 200)
        rep_csv_resp = self.client.get("/reports/csv?type=full")
        self.assertEqual(rep_csv_resp.status_code, 200)
        self.assertIn("CATEGORY-WISE SALES & TAX BREAKDOWN", rep_csv_resp.get_data(as_text=True))

    def test_product_crud_and_rule_configuration_routes(self):
        prod_page = self.client.get("/products/add")
        csrf = self._extract_csrf(prod_page.get_data(as_text=True))

        # Add product via HTTP POST
        add_resp = self.client.post(
            "/products/add",
            data={
                "csrf_token": csrf,
                "product_code": "GRO-888",
                "product_name": "Organic Honey (500g)",
                "category": "Grocery",
                "unit_price": "420.00",
                "available_stock": "25",
                "discount_eligible": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertIn(b"Organic Honey (500g)", add_resp.data)

        created = [p for p in get_products(self.db_path) if p["product_code"] == "GRO-888"][0]

        # Edit product via HTTP POST
        edit_resp = self.client.post(
            f"/products/{created['id']}/edit",
            data={
                "csrf_token": csrf,
                "product_code": "GRO-888",
                "product_name": "Wildflower Honey (500g)",
                "category": "Grocery",
                "unit_price": "450.00",
                "available_stock": "30",
                "discount_eligible": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(edit_resp.status_code, 200)
        self.assertIn(b"Wildflower Honey (500g)", edit_resp.data)

        # Update max concession limit via HTTP POST
        disc_resp = self.client.post(
            "/discount-rules",
            data={
                "csrf_token": csrf,
                "action": "update_settings",
                "store_name": "NovaMart Retail Superstore",
                "store_address": "42 Commerce Avenue",
                "store_phone": "+91 80 4123 7890",
                "store_gstin": "29AABCN1234F1Z5",
                "max_concession_limit": "1500.00",
            },
            follow_redirects=True,
        )
        self.assertEqual(disc_resp.status_code, 200)
        self.assertIn(b"1500.00", disc_resp.data)

        # Update tax rules via HTTP POST (submitting all category rates)
        tax_payload = {"csrf_token": csrf, "action": "update"}
        for rule in get_tax_rules(self.db_path):
            rid = rule["id"]
            tax_payload[f"tax_rate_{rid}"] = "6.00" if rule["category"] == "Grocery" else f"{rule['tax_rate']:.2f}"
            tax_payload[f"description_{rid}"] = rule["description"]
        tax_resp = self.client.post("/tax-rules", data=tax_payload, follow_redirects=True)
        self.assertEqual(tax_resp.status_code, 200)
        self.assertIn(b"Category tax rules updated", tax_resp.data)

        # Delete product via HTTP POST
        del_resp = self.client.post(
            f"/products/{created['id']}/delete",
            data={"csrf_token": csrf},
            follow_redirects=True,
        )
        self.assertEqual(del_resp.status_code, 200)
        self.assertIsNone(get_product_by_id(self.db_path, created["id"]))

    def test_extra_features_nudge_demo_basket_restock_and_cash_change(self):
        # 1. Next discount tier nudge logic
        nudge = get_next_discount_nudge(800.0, DEFAULT_DISCOUNT_RULES)
        self.assertTrue(nudge["has_next"])
        self.assertEqual(nudge["next_percent"], 5.0)
        self.assertEqual(nudge["amount_needed"], 200.0)

        top_nudge = get_next_discount_nudge(6000.0, DEFAULT_DISCOUNT_RULES)
        self.assertFalse(top_nudge["has_next"])
        self.assertEqual(top_nudge["progress_percent"], 100.0)

        # 2. Cash change validation & calculation
        bad_pay, err_msg, _, _ = calculate_cash_change(1500.0, "Cash", "1000")
        self.assertFalse(bad_pay)
        self.assertIn("less than Final Payable", err_msg)

        ok_pay, _, tendered, change = calculate_cash_change(1500.0, "Cash", "2000")
        self.assertTrue(ok_pay)
        self.assertEqual(tendered, 2000.0)
        self.assertEqual(change, 500.0)

        # 3. Quick restock route
        prod = get_products(self.db_path)[0]
        old_stock = prod["available_stock"]
        page = self.client.get("/products")
        csrf = self._extract_csrf(page.get_data(as_text=True))
        restock_resp = self.client.post(
            f"/products/{prod['id']}/restock",
            data={"csrf_token": csrf, "add_units": "10"},
            follow_redirects=True,
        )
        self.assertEqual(restock_resp.status_code, 200)
        self.assertEqual(get_product_by_id(self.db_path, prod["id"])["available_stock"], old_stock + 10)

        # 4. Demo basket preset + Cash checkout with change due
        demo_resp = self.client.post(
            "/billing/load-demo-basket",
            data={"csrf_token": csrf, "preset": "cap_demo"},
            follow_redirects=True,
        )
        self.assertEqual(demo_resp.status_code, 200)
        demo_html = demo_resp.get_data(as_text=True)
        self.assertIn("Capped", demo_html)
        nonce_match = re.search(r'name="checkout_nonce"\s+value="([^"]+)"', demo_html)
        self.assertIsNotNone(nonce_match)

        checkout_resp = self.client.post(
            "/billing/checkout",
            data={
                "csrf_token": csrf,
                "checkout_nonce": nonce_match.group(1),
                "customer_name": "Ananya Rao",
                "payment_mode": "Cash",
                "cash_tendered": "20000.00",
            },
            follow_redirects=True,
        )
        self.assertEqual(checkout_resp.status_code, 200)
        checkout_html = checkout_resp.get_data(as_text=True)
        self.assertIn("Ananya Rao", checkout_html)
        self.assertIn("Change:", checkout_html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
