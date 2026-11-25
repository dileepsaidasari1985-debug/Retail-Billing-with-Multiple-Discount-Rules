# Test Cases — Smart Retail Billing & Discount Management System

The following **22 test cases** validate all billing logic, edge cases, database persistence, and web UI features.

| TC ID | Scenario | Input / Action | Expected Output | Status |
|---|---|---|---|---|
| **TC-01** | Single product billing | 3 × Basmati Rice (`₹540.00`, Grocery 5% tax) | Line subtotal `₹1,620.00`; 5% threshold discount `₹81.00`; Taxable `₹1,539.00`; Tax `₹76.95`; Final `₹1,615.95` | Verified |
| **TC-02** | Multiple product billing | 2 × Earbuds (`₹2,899`, 18% tax) + 2 × Rice (`₹540`, 5% tax) | Subtotal `₹6,878.00`; 15% discount `₹1,031.70` capped to `₹1,000.00`; Category taxes calculated separately | Verified |
| **TC-03** | Quantity validation (zero/negative) | Attempt to add `0` or `-2` units to cart | Rejected with `"Quantity must be at least 1."` | Verified |
| **TC-04** | Stock validation (over-stock) | Product stock = `12`; request `15` units | Rejected with `"Requested quantity (15) exceeds available stock (12)."` | Verified |
| **TC-05** | Category-specific tax calculation | Cart has Grocery (5%) + Electronics (18%) items | Grocery taxed at 5%, Electronics taxed at 18%, displayed in Category Tax Summary | Verified |
| **TC-06** | Zero discount below threshold | Eligible subtotal = `₹999.99` | `discount_percent = 0.0%`, `final_discount = ₹0.00` | Verified |
| **TC-07** | Discount threshold boundary (5%) | Eligible subtotal = `₹1,000.00` and `₹2,499.99` | `discount_percent = 5.0%` (`₹50.00` and `₹125.00`) | Verified |
| **TC-08** | Discount threshold boundary (10%) | Eligible subtotal = `₹2,500.00` and `₹4,999.00` | `discount_percent = 10.0%` (`₹250.00` and `₹499.90`) | Verified |
| **TC-09** | Discount threshold boundary (15%) | Eligible subtotal = `₹5,000.00` | `discount_percent = 15.0%`, `eligible_discount = ₹750.00` | Verified |
| **TC-10** | Maximum concession limit enforcement | Subtotal = `₹8,000.00` (`15% = ₹1,200.00`), Limit = `₹1,000.00` | `final_discount` capped at `₹1,000.00` and `concession_capped = True` | Verified |
| **TC-11** | Non-discountable item exclusion | Calculator (`₹1,500.00`, `discount_eligible=False`) | `eligible_subtotal = ₹0.00`, `final_discount = ₹0.00`, 5% tax `₹75.00`, Final `₹1,575.00` | Verified |
| **TC-12** | Invalid product price | Add product with `unit_price = -10` or `0` | Server-side validation rejects with error message | Verified |
| **TC-13** | Invalid quantity (non-integer) | Submit quantity `"2.5"` or `"abc"` | Server-side validation rejects with integer error | Verified |
| **TC-14** | Duplicate product code prevention | Add product with existing code `GRO-101` | Rejected with `"Product code 'GRO-101' already exists."` | Verified |
| **TC-15** | Final invoice calculation formula | Subtotal `₹8,000`, Discount `₹1,000`, Tax `₹1,032.50` | `8000.00 - 1000.00 + 1032.50 = ₹8,032.50` | Verified |
| **TC-16** | Unique invoice number & refresh safety | Checkout once, then resubmit same `checkout_nonce` | First creates `INV-YYYYMMDD-XXXX`; second is ignored without duplicate invoice | Verified |
| **TC-17** | Database snapshot immutability | Checkout at `₹2,000`, then edit product to `₹3,500` and delete | Historical invoice retains `₹2,000` unit price and original total | Verified |
| **TC-18** | Billing history search, filter, sort | Search by customer/invoice#, filter by date, sort by amount | Matching SQLite records returned in requested order | Verified |
| **TC-19** | CSV exports (Invoice & Reports) | Request `/invoice/<id>/csv` and `/reports/csv?type=full` | Valid UTF-8 CSV downloaded via Python built-in `csv` module | Verified |
| **TC-20** | Product editing & stock update | Edit product name, price, and stock via `/products/<id>/edit` | Changes persisted in `products` table | Verified |
| **TC-21** | Product deletion with confirmation | Confirm deletion in `<dialog>` modal via POST `/delete` | Product removed from catalog and active cart | Verified |
| **TC-22** | Tax & discount rule modification | Update Electronics tax to `20%` and max limit to `₹1,500` | Subsequent bills immediately use new rates and limit; total sales KPI updates | Verified |
