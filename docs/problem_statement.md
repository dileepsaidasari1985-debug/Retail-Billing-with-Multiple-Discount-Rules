# Problem Statement

## Case Study #7: Retail Billing with Multiple Discount Rules

Modern retail supermarkets and multi-category stores handle diverse inventories spanning groceries, electronics, clothing, stationery, and household supplies. Manual billing or naive single-rate billing calculators fail in real retail environments for four primary reasons:

1. **Multi-Category Tax Complexity**: Different product categories carry different statutory or academic tax percentages (for example, Grocery at 5%, Clothing at 8%, Household at 12%, and Electronics at 18%). Applying a single flat tax rate to the entire basket leads to inaccurate invoices.
2. **Threshold-Based Promotional Discounts**: Stores frequently offer tiered discounts based on total eligible purchase value (e.g., 0% below ₹1,000, 5% for ₹1,000–₹2,499, 10% for ₹2,500–₹4,999, and 15% for ₹5,000 and above), while excluding certain non-discountable items.
3. **Maximum Concession Limit Enforcement**: Unbounded percentage discounts on high-value orders can erode profit margins. Stores require an automated upper concession cap (e.g., maximum ₹1,000 discount per invoice) so that `Actual Discount = min(Threshold Discount, Maximum Concession Limit)`.
4. **Inventory Consistency & Historical Auditability**: Billing must validate stock availability in real time, prevent overselling, persist permanent itemized invoices in a relational database, and preserve historical prices and tax rates even when catalog prices or rules are updated later.

The **Smart Retail Billing and Discount Management System** solves these challenges through a Python-powered Flask web application backed by SQLite, delivering real-time cart calculations, configurable tax/discount engines, itemized printable invoices, billing history search, and CSV reporting.
