# Step-by-Step Retail Billing Algorithm

1. **Start**.
2. **Initialize System & Load Data**:
   - Connect to SQLite database `database/retail.db`.
   - Load active products, category tax rules (`{category: tax_rate}`), threshold discount rules `(min_amount, max_amount, discount_percent, label)`, and `max_concession_limit`.
3. **Product Selection & Cart Input**:
   - Cashier/customer searches or browses products and selects `product_id` and `quantity`.
4. **Input & Stock Validation**:
   - Verify `quantity` is a positive integer (`quantity >= 1`).
   - Verify `quantity <= available_stock` (including any units of that product already in the cart).
   - If invalid, display an error message and prompt again.
5. **Line-Item & Subtotal Calculation**:
   - Initialize `purchase_subtotal = 0`, `eligible_subtotal = 0`.
   - For each item in `cart_items`:
     - Compute `line_subtotal = round(unit_price * quantity, 2)`.
     - Add `line_subtotal` to `purchase_subtotal`.
     - If `item.discount_eligible` is `True`, add `line_subtotal` to `eligible_subtotal`.
6. **Threshold Discount Identification**:
   - Sort `discount_rules` ascending by `min_amount`.
   - Loop through each rule tuple `(min_amt, max_amt, pct, label)` and find the matching slab for `eligible_subtotal`.
   - Compute `eligible_discount = round(eligible_subtotal * (pct / 100), 2)`.
7. **Maximum Concession Limit Enforcement**:
   - Compare `eligible_discount` with `max_concession_limit`.
   - Set `final_discount = min(eligible_discount, max_concession_limit)`.
   - Set `concession_capped = (eligible_discount > max_concession_limit)`.
8. **Taxable Amount & Category-Specific Tax Calculation**:
   - Allocate `final_discount` proportionally across discount-eligible line items.
   - For each line item:
     - `item_taxable = round(line_subtotal - item_discount, 2)`.
     - Look up `tax_rate = tax_rules_map[item.category]`.
     - `item_tax = round(item_taxable * (tax_rate / 100), 2)`.
     - `line_total = round(item_taxable + item_tax, 2)`.
     - Accumulate `total_tax += item_tax` and group totals by `category`.
9. **Final Payable Amount**:
   - Compute `taxable_amount = round(purchase_subtotal - final_discount, 2)`.
   - Compute `final_payable = round(purchase_subtotal - final_discount + total_tax, 2)`.
10. **Generate & Persist Itemized Invoice**:
    - Generate unique invoice number `INV-YYYYMMDD-XXXX`.
    - Inside a single SQLite transaction: insert row into `invoices`, insert line-item snapshots into `invoice_items`, and deduct purchased quantities from `products.available_stock`.
11. **Display Invoice, Pattern Summary & Reports**:
    - Render printable itemized invoice, allow CSV download, and update dashboard/report statistics.
12. **End**.
