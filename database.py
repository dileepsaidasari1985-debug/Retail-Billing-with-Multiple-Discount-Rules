"""
SQLite Database Layer - Smart Retail Billing and Discount Management System
---------------------------------------------------------------------------
Automatically creates the SQLite database and all 6 required tables:
1. products
2. category_tax_rules
3. discount_rules
4. invoices
5. invoice_items
6. billing_settings

All queries use parameterized SQL statements to prevent SQL injection.
Historical invoices snapshot product prices, tax rates, and discounts at sale time.
"""

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta

from billing_logic import (
    DEFAULT_DISCOUNT_RULES,
    DEFAULT_SETTINGS,
    DEFAULT_TAX_RULES,
    calculate_invoice,
    generate_invoice_number,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLED_DB_PATH = os.path.join(BASE_DIR, "database", "retail.db")

# 18 sample products spanning Grocery, Electronics, Clothing, Stationery, Household
SAMPLE_PRODUCTS = [
    ("GRO-101", "Basmati Rice (5 kg Bag)", "Grocery", 540.00, 48, 1),
    ("GRO-102", "Cold-Pressed Olive Oil (1 L)", "Grocery", 890.00, 30, 1),
    ("GRO-103", "Organic Almonds (500 g)", "Grocery", 620.00, 40, 1),
    ("GRO-104", "Arabica Filter Coffee (250 g)", "Grocery", 340.00, 55, 1),
    ("ELE-201", "Wireless Optical Mouse", "Electronics", 799.00, 25, 1),
    ("ELE-202", "USB-C Fast Power Bank (20000mAh)", "Electronics", 2199.00, 18, 1),
    ("ELE-203", "Bluetooth Noise-Isolating Earbuds", "Electronics", 2899.00, 15, 1),
    ("ELE-204", "Mechanical Numeric Keypad", "Electronics", 1450.00, 12, 1),
    ("CLO-301", "Cotton Oxford Casual Shirt", "Clothing", 1299.00, 32, 1),
    ("CLO-302", "Slim-Fit Chino Trousers", "Clothing", 1699.00, 24, 1),
    ("CLO-303", "Merino Crew-Neck Pullover", "Clothing", 2299.00, 16, 1),
    ("CLO-304", "Sports Running Socks (Pack of 3)", "Clothing", 399.00, 60, 1),
    ("STA-401", "Hardcover Ruled Notebook (A4)", "Stationery", 240.00, 80, 1),
    ("STA-402", "Gel Ink Rollerball Pens (Box of 10)", "Stationery", 180.00, 95, 1),
    ("STA-403", "Scientific Engineering Calculator", "Stationery", 950.00, 22, 0),
    ("HOU-501", "Stainless Steel Vacuum Flask (1 L)", "Household", 899.00, 35, 1),
    ("HOU-502", "Non-Stick Induction Frypan (26 cm)", "Household", 1599.00, 20, 1),
    ("HOU-503", "Microfiber Spin Mop & Bucket Set", "Household", 1349.00, 14, 1),
]


def resolve_default_db_path():
    """
    Use database/retail.db locally; fall back to writable temp storage if needed.
    """
    db_dir = os.path.dirname(BUNDLED_DB_PATH)
    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
    is_writable = os.path.isdir(db_dir) and os.access(db_dir, os.W_OK)

    if is_serverless or not is_writable:
        tmp_db = os.path.join(tempfile.gettempdir(), "retail.db")
        if not os.path.exists(tmp_db) and os.path.exists(BUNDLED_DB_PATH):
            shutil.copy2(BUNDLED_DB_PATH, tmp_db)
        return tmp_db
    return BUNDLED_DB_PATH


DEFAULT_DB_PATH = resolve_default_db_path()


def get_connection(db_path=DEFAULT_DB_PATH):
    """Create a SQLite connection with Row access and foreign key enforcement."""
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=DEFAULT_DB_PATH, seed_if_empty=True):
    """Initialize SQLite schema, default rules/settings, and optional sample records."""
    conn = get_connection(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL UNIQUE,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL CHECK(unit_price > 0),
                available_stock INTEGER NOT NULL CHECK(available_stock >= 0),
                tax_category TEXT NOT NULL,
                discount_eligible INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS category_tax_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL UNIQUE,
                tax_rate REAL NOT NULL CHECK(tax_rate >= 0 AND tax_rate <= 100),
                description TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS discount_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                min_amount REAL NOT NULL CHECK(min_amount >= 0),
                max_amount REAL,
                discount_percent REAL NOT NULL CHECK(discount_percent >= 0 AND discount_percent <= 100),
                rule_label TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS billing_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                payment_mode TEXT NOT NULL DEFAULT 'Cash',
                cash_tendered REAL NOT NULL DEFAULT 0.0,
                change_due REAL NOT NULL DEFAULT 0.0,
                invoice_datetime TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                total_items INTEGER NOT NULL,
                total_units INTEGER NOT NULL,
                purchase_subtotal REAL NOT NULL,
                eligible_subtotal REAL NOT NULL,
                discount_percent REAL NOT NULL,
                eligible_discount REAL NOT NULL,
                max_concession_limit REAL NOT NULL,
                final_discount REAL NOT NULL,
                concession_capped INTEGER NOT NULL DEFAULT 0,
                taxable_amount REAL NOT NULL,
                total_tax REAL NOT NULL,
                final_payable REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                product_id INTEGER,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                line_subtotal REAL NOT NULL,
                discount_eligible INTEGER NOT NULL,
                discount_amount REAL NOT NULL,
                taxable_amount REAL NOT NULL,
                tax_rate REAL NOT NULL,
                tax_amount REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            );
            """
        )

        # Safe migration for existing databases lacking payment_mode/cash columns
        existing_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(invoices)").fetchall()
        }
        if "payment_mode" not in existing_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN payment_mode TEXT NOT NULL DEFAULT 'Cash'")
        if "cash_tendered" not in existing_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN cash_tendered REAL NOT NULL DEFAULT 0.0")
        if "change_due" not in existing_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN change_due REAL NOT NULL DEFAULT 0.0")

        # Seed default category tax rules if empty
        tax_count = conn.execute("SELECT COUNT(*) FROM category_tax_rules").fetchone()[0]
        if tax_count == 0:
            for category, tax_rate, desc in DEFAULT_TAX_RULES:
                conn.execute(
                    "INSERT INTO category_tax_rules (category, tax_rate, description) VALUES (?, ?, ?)",
                    (category, tax_rate, desc),
                )

        # Seed default discount rules if empty
        disc_count = conn.execute("SELECT COUNT(*) FROM discount_rules").fetchone()[0]
        if disc_count == 0:
            for min_amt, max_amt, pct, label in DEFAULT_DISCOUNT_RULES:
                conn.execute(
                    "INSERT INTO discount_rules (min_amount, max_amount, discount_percent, rule_label) VALUES (?, ?, ?, ?)",
                    (min_amt, max_amt, pct, label),
                )

        # Seed billing settings if missing
        for key, val in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO billing_settings (setting_key, setting_value) VALUES (?, ?)",
                (key, str(val)),
            )

        conn.commit()

        if seed_if_empty:
            prod_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if prod_count == 0:
                load_sample_data(db_path, include_invoices=True)
    finally:
        conn.close()


def load_sample_data(db_path=DEFAULT_DB_PATH, include_invoices=True):
    """
    Insert sample retail products and initial sample invoices without duplicating
    any existing product codes or invoice numbers.
    Returns (added_products_count, added_invoices_count).
    """
    conn = get_connection(db_path)
    added_products = 0
    added_invoices = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        for code, name, cat, price, stock, eligible in SAMPLE_PRODUCTS:
            existing = conn.execute(
                "SELECT id FROM products WHERE product_code = ?", (code,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO products
                    (product_code, product_name, category, unit_price, available_stock, tax_category, discount_eligible, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (code, name, cat, price, stock, cat, eligible, now_str),
                )
                added_products += 1
        conn.commit()

        if include_invoices:
            existing_inv = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
            if existing_inv == 0:
                sample_baskets = [
                    (
                        "Aarav Sharma",
                        "Card",
                        0,
                        [("ELE-203", 2), ("CLO-303", 1), ("GRO-101", 2)],
                    ),
                    (
                        "Priya Nair",
                        "UPI",
                        0,
                        [("CLO-301", 1), ("HOU-502", 1), ("STA-401", 3)],
                    ),
                    (
                        "Rohan Deshmukh",
                        "Cash",
                        1,
                        [("GRO-102", 1), ("GRO-104", 2), ("STA-402", 2)],
                    ),
                    (
                        "Sneha Kulkarni",
                        "UPI",
                        2,
                        [("ELE-202", 1), ("HOU-501", 2)],
                    ),
                    (
                        "Walk-in Customer",
                        "Cash",
                        3,
                        [("GRO-103", 1), ("STA-403", 1)],
                    ),
                ]
                tax_map = get_tax_rules_map(db_path)
                disc_rules = get_discount_rules_tuples(db_path)
                settings = get_billing_settings(db_path)
                max_limit = float(settings["max_concession_limit"])

                for seq_idx, (cust_name, pay_mode, days_ago, items_spec) in enumerate(sample_baskets, start=1):
                    dt = datetime.now() - timedelta(days=days_ago)
                    cart_items = []
                    for code, qty in items_spec:
                        prod = conn.execute(
                            "SELECT * FROM products WHERE product_code = ?", (code,)
                        ).fetchone()
                        if prod and prod["available_stock"] >= qty:
                            cart_items.append({
                                "product_id": prod["id"],
                                "product_code": prod["product_code"],
                                "product_name": prod["product_name"],
                                "category": prod["category"],
                                "unit_price": prod["unit_price"],
                                "quantity": qty,
                                "discount_eligible": bool(prod["discount_eligible"]),
                            })

                    if not cart_items:
                        continue

                    bill = calculate_invoice(cart_items, tax_map, disc_rules, max_limit)
                    inv_number = generate_invoice_number(seq_idx, dt)
                    inv_dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    inv_date_str = dt.strftime("%Y-%m-%d")

                    cur = conn.execute(
                        """
                        INSERT INTO invoices (
                            invoice_number, customer_name, payment_mode, cash_tendered, change_due,
                            invoice_datetime, invoice_date,
                            total_items, total_units, purchase_subtotal, eligible_subtotal,
                            discount_percent, eligible_discount, max_concession_limit,
                            final_discount, concession_capped, taxable_amount, total_tax, final_payable
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            inv_number,
                            cust_name,
                            pay_mode,
                            bill["final_payable"],
                            0.0,
                            inv_dt_str,
                            inv_date_str,
                            bill["total_items_count"],
                            bill["total_units"],
                            bill["purchase_subtotal"],
                            bill["eligible_subtotal"],
                            bill["discount_percent"],
                            bill["eligible_discount"],
                            bill["max_concession_limit"],
                            bill["final_discount"],
                            1 if bill["concession_capped"] else 0,
                            bill["taxable_amount"],
                            bill["total_tax"],
                            bill["final_payable"],
                        ),
                    )
                    invoice_id = cur.lastrowid
                    for item in bill["line_items"]:
                        conn.execute(
                            """
                            INSERT INTO invoice_items (
                                invoice_id, product_id, product_code, product_name, category,
                                unit_price, quantity, line_subtotal, discount_eligible,
                                discount_amount, taxable_amount, tax_rate, tax_amount, line_total
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                invoice_id,
                                item["product_id"],
                                item["product_code"],
                                item["product_name"],
                                item["category"],
                                item["unit_price"],
                                item["quantity"],
                                item["line_subtotal"],
                                1 if item["discount_eligible"] else 0,
                                item["discount_amount"],
                                item["taxable_amount"],
                                item["tax_rate"],
                                item["tax_amount"],
                                item["line_total"],
                            ),
                        )
                        conn.execute(
                            "UPDATE products SET available_stock = available_stock - ? WHERE id = ?",
                            (item["quantity"], item["product_id"]),
                        )
                    added_invoices += 1
                conn.commit()
    finally:
        conn.close()

    return (added_products, added_invoices)


def count_missing_sample_products(db_path=DEFAULT_DB_PATH):
    """Return how many sample products are not yet present in the database."""
    conn = get_connection(db_path)
    try:
        existing_codes = {
            row["product_code"]
            for row in conn.execute("SELECT product_code FROM products").fetchall()
        }
        return sum(1 for item in SAMPLE_PRODUCTS if item[0] not in existing_codes)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Product CRUD Operations
# ---------------------------------------------------------------------------
def get_products(db_path=DEFAULT_DB_PATH, search="", category="", sort_by="name_asc"):
    """Fetch products with optional search, category filter, and price/name sorting."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM products WHERE 1=1"
        params = []

        if search:
            like = f"%{search.strip()}%"
            query += " AND (product_name LIKE ? OR product_code LIKE ?)"
            params.extend([like, like])

        if category:
            query += " AND category = ?"
            params.append(category.strip())

        order_map = {
            "price_asc": "unit_price ASC, product_name ASC",
            "price_desc": "unit_price DESC, product_name ASC",
            "stock_asc": "available_stock ASC, product_name ASC",
            "newest": "id DESC",
            "name_asc": "product_name ASC",
        }
        query += f" ORDER BY {order_map.get(sort_by, 'product_name ASC')}"
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def get_product_by_id(db_path, product_id):
    """Fetch a single product by primary key ID."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (int(product_id),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_product(db_path, product_code, product_name, category, unit_price, available_stock, discount_eligible=True):
    """Insert a new product; prevents duplicate product codes."""
    conn = get_connection(db_path)
    try:
        code_upper = product_code.strip().upper()
        dup = conn.execute(
            "SELECT id FROM products WHERE product_code = ?", (code_upper,)
        ).fetchone()
        if dup:
            return (False, f"Product code '{code_upper}' already exists.", None)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """
            INSERT INTO products
            (product_code, product_name, category, unit_price, available_stock, tax_category, discount_eligible, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code_upper,
                product_name.strip(),
                category.strip(),
                round(float(unit_price), 2),
                int(available_stock),
                category.strip(),
                1 if discount_eligible else 0,
                now_str,
            ),
        )
        conn.commit()
        return (True, "Product added successfully.", cur.lastrowid)
    finally:
        conn.close()


def update_product(db_path, product_id, product_code, product_name, category, unit_price, available_stock, discount_eligible=True):
    """Update an existing product; enforces unique product_code across other rows."""
    conn = get_connection(db_path)
    try:
        code_upper = product_code.strip().upper()
        dup = conn.execute(
            "SELECT id FROM products WHERE product_code = ? AND id != ?",
            (code_upper, int(product_id)),
        ).fetchone()
        if dup:
            return (False, f"Another product already uses code '{code_upper}'.")

        cur = conn.execute(
            """
            UPDATE products
            SET product_code = ?, product_name = ?, category = ?, unit_price = ?,
                available_stock = ?, tax_category = ?, discount_eligible = ?
            WHERE id = ?
            """,
            (
                code_upper,
                product_name.strip(),
                category.strip(),
                round(float(unit_price), 2),
                int(available_stock),
                category.strip(),
                1 if discount_eligible else 0,
                int(product_id),
            ),
        )
        conn.commit()
        if cur.rowcount == 0:
            return (False, "Product not found.")
        return (True, "Product updated successfully.")
    finally:
        conn.close()


def delete_product(db_path, product_id):
    """Delete a product from the catalog (existing invoice snapshots remain intact)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM products WHERE id = ?", (int(product_id),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def restock_product(db_path, product_id, add_units=10):
    """Quickly add stock units to an existing product."""
    units = int(add_units)
    if units <= 0:
        return (False, "Restock quantity must be positive.")
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE products SET available_stock = available_stock + ? WHERE id = ?",
            (units, int(product_id)),
        )
        conn.commit()
        if cur.rowcount == 0:
            return (False, "Product not found.")
        return (True, f"Added {units} units to stock.")
    finally:
        conn.close()


def get_low_stock_products(db_path=DEFAULT_DB_PATH, threshold=10):
    """Return products whose available stock is at or below the threshold."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM products WHERE available_stock <= ? ORDER BY available_stock ASC, product_name ASC",
            (int(threshold),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tax Rules, Discount Rules, and Settings
# ---------------------------------------------------------------------------
def get_tax_rules(db_path=DEFAULT_DB_PATH):
    """Return list of category tax rule dicts."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM category_tax_rules ORDER BY category ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tax_rules_map(db_path=DEFAULT_DB_PATH):
    """Return mapping {category: tax_rate}."""
    return {row["category"]: float(row["tax_rate"]) for row in get_tax_rules(db_path)}


def update_tax_rule(db_path, rule_id, tax_rate, description=""):
    """Update tax rate for a category rule."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE category_tax_rules SET tax_rate = ?, description = ? WHERE id = ?",
            (round(float(tax_rate), 2), str(description).strip(), int(rule_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def reset_tax_rules(db_path=DEFAULT_DB_PATH):
    """Restore default category tax rates."""
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM category_tax_rules")
        for category, tax_rate, desc in DEFAULT_TAX_RULES:
            conn.execute(
                "INSERT INTO category_tax_rules (category, tax_rate, description) VALUES (?, ?, ?)",
                (category, tax_rate, desc),
            )
        conn.commit()
    finally:
        conn.close()


def get_discount_rules(db_path=DEFAULT_DB_PATH):
    """Return list of discount rule dicts sorted by min_amount."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM discount_rules ORDER BY min_amount ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_discount_rules_tuples(db_path=DEFAULT_DB_PATH):
    """Return discount rules as list of tuples for calculate_threshold_discount()."""
    rules = get_discount_rules(db_path)
    return [
        (float(r["min_amount"]), float(r["max_amount"]) if r["max_amount"] is not None else None, float(r["discount_percent"]), r["rule_label"])
        for r in rules
    ]


def add_discount_rule(db_path, min_amount, max_amount, discount_percent, rule_label=""):
    """Insert a new threshold discount rule."""
    conn = get_connection(db_path)
    try:
        label = rule_label.strip() or (
            f"₹{min_amount:,.0f} and above ({discount_percent:.1f}% Off)"
            if max_amount is None
            else f"₹{min_amount:,.0f} – ₹{max_amount:,.0f} ({discount_percent:.1f}% Off)"
        )
        conn.execute(
            "INSERT INTO discount_rules (min_amount, max_amount, discount_percent, rule_label) VALUES (?, ?, ?, ?)",
            (round(float(min_amount), 2), round(float(max_amount), 2) if max_amount is not None else None, round(float(discount_percent), 2), label),
        )
        conn.commit()
    finally:
        conn.close()


def update_discount_rule(db_path, rule_id, min_amount, max_amount, discount_percent, rule_label=""):
    """Update an existing discount tier."""
    conn = get_connection(db_path)
    try:
        label = rule_label.strip() or (
            f"₹{min_amount:,.0f} and above ({discount_percent:.1f}% Off)"
            if max_amount is None
            else f"₹{min_amount:,.0f} – ₹{max_amount:,.0f} ({discount_percent:.1f}% Off)"
        )
        cur = conn.execute(
            """
            UPDATE discount_rules
            SET min_amount = ?, max_amount = ?, discount_percent = ?, rule_label = ?
            WHERE id = ?
            """,
            (
                round(float(min_amount), 2),
                round(float(max_amount), 2) if max_amount is not None else None,
                round(float(discount_percent), 2),
                label,
                int(rule_id),
            ),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_discount_rule(db_path, rule_id):
    """Delete a discount tier."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM discount_rules WHERE id = ?", (int(rule_id),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def reset_discount_rules(db_path=DEFAULT_DB_PATH):
    """Restore default threshold discount rules and concession limit."""
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM discount_rules")
        for min_amt, max_amt, pct, label in DEFAULT_DISCOUNT_RULES:
            conn.execute(
                "INSERT INTO discount_rules (min_amount, max_amount, discount_percent, rule_label) VALUES (?, ?, ?, ?)",
                (min_amt, max_amt, pct, label),
            )
        conn.execute(
            "INSERT OR REPLACE INTO billing_settings (setting_key, setting_value) VALUES (?, ?)",
            ("max_concession_limit", str(DEFAULT_SETTINGS["max_concession_limit"])),
        )
        conn.commit()
    finally:
        conn.close()


def get_billing_settings(db_path=DEFAULT_DB_PATH):
    """Fetch store metadata and max concession limit as a dictionary."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT setting_key, setting_value FROM billing_settings").fetchall()
        settings = dict(DEFAULT_SETTINGS)
        for row in rows:
            settings[row["setting_key"]] = row["setting_value"]
        settings["max_concession_limit"] = round(float(settings["max_concession_limit"]), 2)
        return settings
    finally:
        conn.close()


def update_billing_settings(db_path, store_name, store_address, store_phone, store_gstin, max_concession_limit):
    """Persist updated store info and maximum concession limit."""
    conn = get_connection(db_path)
    try:
        updates = {
            "store_name": str(store_name).strip() or DEFAULT_SETTINGS["store_name"],
            "store_address": str(store_address).strip() or DEFAULT_SETTINGS["store_address"],
            "store_phone": str(store_phone).strip() or DEFAULT_SETTINGS["store_phone"],
            "store_gstin": str(store_gstin).strip().upper() or DEFAULT_SETTINGS["store_gstin"],
            "max_concession_limit": str(round(float(max_concession_limit), 2)),
        }
        for k, v in updates.items():
            conn.execute(
                "INSERT OR REPLACE INTO billing_settings (setting_key, setting_value) VALUES (?, ?)",
                (k, v),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Invoice Creation, History, and Reporting
# ---------------------------------------------------------------------------
def create_invoice_from_cart(
    db_path,
    cart_quantities_map,
    customer_name="Walk-in Customer",
    payment_mode="Cash",
    cash_tendered=None,
    change_due=0.0,
):
    """
    Validate live stock, run Python billing engine, persist invoice + line items,
    and deduct stock inside one atomic SQLite transaction.

    cart_quantities_map: dict {product_id (int): quantity (int)}
    Returns (success, message, invoice_id)
    """
    if not cart_quantities_map:
        return (False, "Cart is empty. Add at least one product before billing.", None)

    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cart_items = []

        for prod_id, qty in cart_quantities_map.items():
            prod = conn.execute(
                "SELECT * FROM products WHERE id = ?", (int(prod_id),)
            ).fetchone()
            if prod is None:
                conn.rollback()
                return (False, f"Product ID {prod_id} no longer exists.", None)

            qty_int = int(qty)
            if qty_int <= 0:
                conn.rollback()
                return (False, f"Invalid quantity for {prod['product_name']}.", None)
            if qty_int > prod["available_stock"]:
                conn.rollback()
                return (
                    False,
                    f"Insufficient stock for {prod['product_name']} (available: {prod['available_stock']}).",
                    None,
                )

            cart_items.append({
                "product_id": prod["id"],
                "product_code": prod["product_code"],
                "product_name": prod["product_name"],
                "category": prod["category"],
                "unit_price": float(prod["unit_price"]),
                "quantity": qty_int,
                "discount_eligible": bool(prod["discount_eligible"]),
            })

        tax_rows = conn.execute("SELECT category, tax_rate FROM category_tax_rules").fetchall()
        tax_map = {r["category"]: float(r["tax_rate"]) for r in tax_rows}

        disc_rows = conn.execute(
            "SELECT min_amount, max_amount, discount_percent, rule_label FROM discount_rules ORDER BY min_amount ASC"
        ).fetchall()
        disc_rules = [
            (float(r["min_amount"]), float(r["max_amount"]) if r["max_amount"] is not None else None, float(r["discount_percent"]), r["rule_label"])
            for r in disc_rows
        ]

        limit_row = conn.execute(
            "SELECT setting_value FROM billing_settings WHERE setting_key = 'max_concession_limit'"
        ).fetchone()
        max_limit = float(limit_row["setting_value"]) if limit_row else DEFAULT_SETTINGS["max_concession_limit"]

        bill = calculate_invoice(cart_items, tax_map, disc_rules, max_limit)

        now_dt = datetime.now()
        inv_datetime = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        inv_date = now_dt.strftime("%Y-%m-%d")

        max_id_row = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM invoices").fetchone()
        next_seq = int(max_id_row["max_id"]) + 1
        inv_number = generate_invoice_number(next_seq, now_dt)

        # Ensure uniqueness even if rows were manually removed
        while conn.execute("SELECT id FROM invoices WHERE invoice_number = ?", (inv_number,)).fetchone():
            next_seq += 1
            inv_number = generate_invoice_number(next_seq, now_dt)

        cust_clean = str(customer_name or "").strip() or "Walk-in Customer"
        mode_clean = str(payment_mode or "Cash").strip() or "Cash"
        tendered_val = round(float(cash_tendered), 2) if cash_tendered is not None else bill["final_payable"]
        change_val = round(float(change_due), 2)

        cur = conn.execute(
            """
            INSERT INTO invoices (
                invoice_number, customer_name, payment_mode, cash_tendered, change_due,
                invoice_datetime, invoice_date,
                total_items, total_units, purchase_subtotal, eligible_subtotal,
                discount_percent, eligible_discount, max_concession_limit,
                final_discount, concession_capped, taxable_amount, total_tax, final_payable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inv_number,
                cust_clean,
                mode_clean,
                tendered_val,
                change_val,
                inv_datetime,
                inv_date,
                bill["total_items_count"],
                bill["total_units"],
                bill["purchase_subtotal"],
                bill["eligible_subtotal"],
                bill["discount_percent"],
                bill["eligible_discount"],
                bill["max_concession_limit"],
                bill["final_discount"],
                1 if bill["concession_capped"] else 0,
                bill["taxable_amount"],
                bill["total_tax"],
                bill["final_payable"],
            ),
        )
        invoice_id = cur.lastrowid

        for item in bill["line_items"]:
            conn.execute(
                """
                INSERT INTO invoice_items (
                    invoice_id, product_id, product_code, product_name, category,
                    unit_price, quantity, line_subtotal, discount_eligible,
                    discount_amount, taxable_amount, tax_rate, tax_amount, line_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    item["product_id"],
                    item["product_code"],
                    item["product_name"],
                    item["category"],
                    item["unit_price"],
                    item["quantity"],
                    item["line_subtotal"],
                    1 if item["discount_eligible"] else 0,
                    item["discount_amount"],
                    item["taxable_amount"],
                    item["tax_rate"],
                    item["tax_amount"],
                    item["line_total"],
                ),
            )
            conn.execute(
                "UPDATE products SET available_stock = available_stock - ? WHERE id = ?",
                (item["quantity"], item["product_id"]),
            )

        conn.commit()
        return (True, f"Invoice {inv_number} generated successfully.", invoice_id)
    except Exception as exc:
        conn.rollback()
        return (False, f"Failed to generate invoice: {exc}", None)
    finally:
        conn.close()


def get_invoice_by_id(db_path, invoice_id):
    """Fetch an invoice header, its line items, and category-wise tax summary."""
    conn = get_connection(db_path)
    try:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (int(invoice_id),)).fetchone()
        if inv is None:
            return None

        items = conn.execute(
            "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id ASC",
            (int(invoice_id),),
        ).fetchall()

        cat_rows = conn.execute(
            """
            SELECT category, tax_rate,
                   ROUND(SUM(line_subtotal), 2) AS subtotal,
                   ROUND(SUM(discount_amount), 2) AS discount_amount,
                   ROUND(SUM(taxable_amount), 2) AS taxable_amount,
                   ROUND(SUM(tax_amount), 2) AS tax_amount,
                   ROUND(SUM(line_total), 2) AS total_with_tax
            FROM invoice_items
            WHERE invoice_id = ?
            GROUP BY category, tax_rate
            ORDER BY category ASC
            """,
            (int(invoice_id),),
        ).fetchall()

        return {
            "invoice": dict(inv),
            "items": [dict(r) for r in items],
            "category_summary": [dict(r) for r in cat_rows],
        }
    finally:
        conn.close()


def get_invoices(db_path=DEFAULT_DB_PATH, search="", filter_date="", sort_by="newest"):
    """Fetch billing history with search (invoice# / customer), date filter, and sort."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM invoices WHERE 1=1"
        params = []

        if search:
            like = f"%{search.strip()}%"
            query += " AND (invoice_number LIKE ? OR customer_name LIKE ?)"
            params.extend([like, like])

        if filter_date:
            query += " AND invoice_date = ?"
            params.append(filter_date.strip())

        order_map = {
            "amount_desc": "final_payable DESC, id DESC",
            "amount_asc": "final_payable ASC, id DESC",
            "oldest": "id ASC",
            "newest": "id DESC",
        }
        query += f" ORDER BY {order_map.get(sort_by, 'id DESC')}"
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def get_dashboard_and_report_stats(db_path=DEFAULT_DB_PATH):
    """Compute live dashboard KPIs, discount stats, and category sales/tax reports from SQLite."""
    conn = get_connection(db_path)
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")

        total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        low_stock_count = conn.execute("SELECT COUNT(*) FROM products WHERE available_stock <= 10").fetchone()[0]

        agg = conn.execute(
            """
            SELECT
                COUNT(*) AS total_invoices,
                COALESCE(ROUND(SUM(final_payable), 2), 0.0) AS total_sales,
                COALESCE(ROUND(SUM(purchase_subtotal), 2), 0.0) AS gross_subtotal,
                COALESCE(ROUND(SUM(final_discount), 2), 0.0) AS total_discounts,
                COALESCE(ROUND(SUM(total_tax), 2), 0.0) AS total_tax,
                COALESCE(ROUND(AVG(final_payable), 2), 0.0) AS avg_invoice,
                COALESCE(ROUND(MAX(final_payable), 2), 0.0) AS highest_invoice,
                COALESCE(SUM(CASE WHEN concession_capped = 1 THEN 1 ELSE 0 END), 0) AS capped_invoices,
                COALESCE(ROUND(SUM(CASE WHEN eligible_discount > final_discount THEN eligible_discount - final_discount ELSE 0 END), 2), 0.0) AS concession_saved_by_cap
            FROM invoices
            """
        ).fetchone()

        today_row = conn.execute(
            """
            SELECT
                COUNT(*) AS today_invoices,
                COALESCE(ROUND(SUM(final_payable), 2), 0.0) AS today_sales
            FROM invoices
            WHERE invoice_date = ?
            """,
            (today_str,),
        ).fetchone()

        top_product_row = conn.execute(
            """
            SELECT product_name, product_code, category,
                   SUM(quantity) AS total_qty,
                   ROUND(SUM(line_total), 2) AS total_revenue
            FROM invoice_items
            GROUP BY product_code, product_name, category
            ORDER BY total_qty DESC, total_revenue DESC
            LIMIT 1
            """
        ).fetchone()

        category_breakdown = conn.execute(
            """
            SELECT category,
                   COUNT(DISTINCT invoice_id) AS invoice_count,
                   SUM(quantity) AS units_sold,
                   ROUND(SUM(line_subtotal), 2) AS gross_sales,
                   ROUND(SUM(discount_amount), 2) AS discounts_given,
                   ROUND(SUM(tax_amount), 2) AS tax_collected,
                   ROUND(SUM(line_total), 2) AS net_sales
            FROM invoice_items
            GROUP BY category
            ORDER BY net_sales DESC
            """
        ).fetchall()

        recent_invoices = conn.execute(
            "SELECT * FROM invoices ORDER BY id DESC LIMIT 6"
        ).fetchall()

        discount_tier_stats = conn.execute(
            """
            SELECT
                CASE
                    WHEN discount_percent = 0 THEN '0% (No Threshold)'
                    ELSE printf('%.0f%% Tier', discount_percent)
                END AS tier_label,
                COUNT(*) AS invoice_count,
                ROUND(SUM(final_discount), 2) AS total_discount
            FROM invoices
            GROUP BY discount_percent
            ORDER BY discount_percent ASC
            """
        ).fetchall()

        payment_mode_stats = conn.execute(
            """
            SELECT payment_mode,
                   COUNT(*) AS invoice_count,
                   ROUND(SUM(final_payable), 2) AS total_collected
            FROM invoices
            GROUP BY payment_mode
            ORDER BY total_collected DESC
            """
        ).fetchall()

        cat_list = [dict(r) for r in category_breakdown]
        max_cat_sales = max((c["net_sales"] for c in cat_list), default=0.0)
        for c in cat_list:
            c["share_percent"] = round((c["net_sales"] / max_cat_sales) * 100.0, 1) if max_cat_sales > 0 else 0.0

        return {
            "total_products": int(total_products),
            "low_stock_count": int(low_stock_count),
            "total_invoices": int(agg["total_invoices"]),
            "total_sales": float(agg["total_sales"]),
            "gross_subtotal": float(agg["gross_subtotal"]),
            "total_discounts": float(agg["total_discounts"]),
            "total_tax": float(agg["total_tax"]),
            "avg_invoice": float(agg["avg_invoice"]),
            "highest_invoice": float(agg["highest_invoice"]),
            "capped_invoices": int(agg["capped_invoices"]),
            "concession_saved_by_cap": float(agg["concession_saved_by_cap"]),
            "today_invoices": int(today_row["today_invoices"]),
            "today_sales": float(today_row["today_sales"]),
            "top_product": dict(top_product_row) if top_product_row else None,
            "category_breakdown": cat_list,
            "recent_invoices": [dict(r) for r in recent_invoices],
            "discount_tier_stats": [dict(r) for r in discount_tier_stats],
            "payment_mode_stats": [dict(r) for r in payment_mode_stats],
        }
    finally:
        conn.close()
