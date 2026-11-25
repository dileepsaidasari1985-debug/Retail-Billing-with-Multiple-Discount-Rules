# Smart Retail Billing and Discount Management System

**Case Study #7:** *Retail Billing with Multiple Discount Rules — Process multiple products, quantities, category-specific taxes, threshold discounts, and maximum concession limits to generate an itemized invoice.*

A complete, responsive, beginner-friendly **Python + Flask + SQLite** retail POS billing and discount management web application built for a Python Activity-Based Learning college assignment.

## Key Features

- **Live SQLite Dashboard**: Total sales, today's sales, total discounts given, concession-cap statistics, total tax collected, average/highest invoice value, and recent invoices.
- **Product Catalog Management**: Add, edit, delete (with modal confirmation), search, filter by category, sort by price/stock, prevent duplicate product codes, and load 18 sample products without duplication.
- **POS Billing Counter & Shopping Cart**: Multi-product selection, real-time stock limits, increment/decrement/remove controls, live backend Python bill breakdown, and duplicate-safe checkout.
- **Category-Specific Tax Engine**: Configurable tax percentages per category (`Grocery: 5%`, `Clothing: 8%`, `Stationery: 5%`, `Household: 12%`, `Electronics: 18%`).
- **Threshold Discount & Maximum Concession Engine**: Configurable purchase subtotal slabs (`0%`, `5%`, `10%`, `15%`) powered by `calculate_threshold_discount(subtotal, discount_rules)`, capped by an editable per-invoice maximum concession limit (`₹1,000.00` default).
- **Itemized Printable Invoices & CSV Exports**: Unique `INV-YYYYMMDD-XXXX` numbers, print-optimized layout, Python ASCII receipt pattern preview, and built-in `csv` exports for both individual invoices and sales reports.
- **Billing History & Sales Reports**: Searchable/sortable invoice archive, category-wise sales & tax table, and most frequently sold product analytics.

## Python Syllabus Concepts Demonstrated

- **Variables & Data Types**: Prices (`float`), stock/quantities (`int`), product codes & invoice numbers (`str`), eligibility flags (`bool`).
- **Operators**: Arithmetic (`+`, `-`, `*`, `/`) and comparisons (`<=`, `>=`, `==`, `min()`).
- **Conditionals & Loops**: Tier matching, validation checks, cart aggregation, and line-item processing.
- **Strings & Pattern Generation**: Formatted `INV-YYYYMMDD-XXXX` numbers, uppercase SKU codes, and `generate_receipt_pattern()` ASCII receipt summary.
- **Lists & Nested Lists**: Cart item lists and `nested_line_items` (`[code, name, category, qty, unit_price, line_subtotal, discount, tax_rate, tax_amount, line_total]`).
- **Tuples, Operations & Unpacking**: `CATEGORIES`, `DEFAULT_TAX_RULES`, `DEFAULT_DISCOUNT_RULES`, and unpacking `(min_amt, max_amt, pct, label)` during threshold evaluation.

## Project Structure

```text
retail-billing-system/
├── app.py                  # Flask routes, CSRF protection, cart session, CSV exports
├── billing_logic.py        # Core Python billing, discount, concession & tax engine
├── database.py             # SQLite schema, parameterized queries & sample data seeder
├── requirements.txt        # Flask>=3.0.0
├── database/
│   └── retail.db           # Auto-created SQLite database
├── templates/              # Jinja2 HTML5 templates (10 pages)
├── static/
│   ├── css/style.css       # Responsive Navy/Royal Blue/Green/Orange POS theme + @media print
│   ├── js/script.js        # Mobile drawer, delete modal <dialog>, print handler
│   └── images/             # NovaMart SVG emblem
├── tests/
│   └── test_billing.py     # Python unittest suite
└── docs/                   # College assignment submission documentation
```

## Setup & Running Locally

```powershell
cd retail-billing-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Running Automated Tests

```powershell
python -m unittest discover -s tests -v
```
