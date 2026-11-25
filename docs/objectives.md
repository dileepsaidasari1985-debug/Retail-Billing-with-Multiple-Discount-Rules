# Project Objectives

The primary objectives of the **Smart Retail Billing and Discount Management System** are:

1. **Manage Multiple Retail Products**: Provide full Create, Read, Update, and Delete (CRUD) operations for retail inventory with unique SKU product codes, category mapping, unit pricing, stock quantities, and discount eligibility flags.
2. **Interactive Multi-Product Shopping Cart**: Allow cashiers/customers to search products by name or code, add multiple items, increment/decrement quantities, and enforce live stock limits.
3. **Product-Wise & Total Price Calculations**: Compute exact line-item subtotals (`unit_price × quantity`) and overall basket subtotals using Python backend logic.
4. **Category-Specific Tax Engine**: Support configurable tax percentages per product category (Grocery, Clothing, Electronics, Stationery, Household) and calculate taxes accurately per category.
5. **Threshold-Based Discount Engine**: Implement `calculate_threshold_discount(subtotal, discount_rules)` using Python loops, conditionals, and tuple unpacking to select and compute the applicable discount slab.
6. **Maximum Concession Enforcement**: Enforce an administrator-configurable maximum discount cap per invoice (`₹1,000.00` by default) so promotional discounts never exceed business limits.
7. **Transparent Final Bill Computation**: Follow the exact formula `Final Payable = Product Subtotal - Discount Applied + Category Taxes` with 2-decimal-place rounding.
8. **Itemized Invoice Generation**: Generate unique, duplicate-safe, print-ready tax invoices with store metadata, itemized breakdown, category tax summary, and CSV download.
9. **Persistent SQLite Storage**: Store products, rules, settings, invoices, and sale-time item snapshots permanently using parameterized SQL queries.
10. **Billing History & Analytical Reports**: Provide searchable/sortable invoice history, live dashboard KPIs, category-wise sales/tax breakdowns, and built-in Python `csv` report exports.
11. **Demonstrate Core Python Syllabus Concepts**: Naturally integrate variables, data types, operators, conditionals, loops, strings, pattern generation, lists, nested lists, tuples, tuple operations, and tuple unpacking.
