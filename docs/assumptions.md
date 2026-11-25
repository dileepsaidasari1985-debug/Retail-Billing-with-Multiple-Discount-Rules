# Project Assumptions & Business Rules

## 1. Product Categories & Academic Example Tax Rates

The system models five retail categories with academic example tax rates (configurable by the administrator; these are academic project values and not official statutory GST advice):

| Category | Default Example Tax Rate | Example Products |
|---|---:|---|
| Grocery | 5% | Basmati Rice, Olive Oil, Organic Almonds, Filter Coffee |
| Clothing | 8% | Cotton Oxford Shirt, Chino Trousers, Merino Pullover, Socks |
| Electronics | 18% | Wireless Mouse, Power Bank, Bluetooth Earbuds, Keypad |
| Stationery | 5% | Hardcover Notebook, Gel Pens, Scientific Calculator |
| Household | 12% | Vacuum Flask, Induction Frypan, Spin Mop Set |

## 2. Threshold-Based Discount Rules

Default purchase subtotal discount slabs (evaluated against the **discount-eligible subtotal**):

| Eligible Purchase Subtotal | Discount Percentage |
|---|---:|
| Below ₹1,000 (`₹0.00 – ₹999.99`) | 0% |
| ₹1,000 – ₹2,499 (`₹1,000.00 – ₹2,499.99`) | 5% |
| ₹2,500 – ₹4,999 (`₹2,500.00 – ₹4,999.99`) | 10% |
| ₹5,000 and above (`≥ ₹5,000.00`) | 15% |

## 3. Maximum Concession Limit

- Default maximum concession per invoice is **₹1,000.00**.
- Formula: `Final Discount Applied = min(Eligible Threshold Discount, Maximum Concession Limit)`.
- Administrators can update this limit from the **Discount & Concession** page.

## 4. Billing & Tax Calculation Rules

1. Line subtotal for each item: `line_subtotal = round(unit_price * quantity, 2)`.
2. Total purchase subtotal: sum of all `line_subtotal` values.
3. Discount-eligible subtotal: sum of `line_subtotal` for items where `discount_eligible = True`.
4. Threshold discount is computed on `eligible_subtotal`, then capped by `max_concession_limit`.
5. The applied `final_discount` is distributed proportionally across discount-eligible line items (with any 1-paisa rounding remainder assigned to the last eligible item so the line discounts sum identically to `final_discount`).
6. Each item's taxable amount is `item_taxable = round(line_subtotal - item_discount, 2)`.
7. Category-specific tax is computed as `item_tax = round(item_taxable * (tax_rate / 100), 2)`.
8. Final payable amount: `Final Payable = Product Subtotal - Final Discount Applied + Category Taxes`.
9. Negative prices, negative quantities, stock over-allocation, duplicate product codes, and tax/discount percentages outside `0–100%` are rejected on the server.
10. Completed invoices snapshot unit price, tax rate, and discount at sale time so later catalog edits never alter historical bills.
