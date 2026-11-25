"""
Billing & Discount Engine - Smart Retail Billing System (Case Study #7)
-----------------------------------------------------------------------
Implements core retail billing calculations using beginner-friendly Python
concepts from the syllabus:
- Variables, data types, and arithmetic/comparison operators
- Conditional statements (if / elif / else)
- Loops (for loops over lists, nested lists, and tuples)
- Strings (codes, invoice numbers, formatting, and pattern generation)
- Lists and nested lists (cart items and itemized invoice line items)
- Tuples, tuple operations, and tuple unpacking (tax rules & discount tiers)
"""

from datetime import datetime

# Supported retail product categories (Tuple - immutable sequence)
CATEGORIES = ("Grocery", "Clothing", "Electronics", "Stationery", "Household")

# Supported payment modes (Tuple)
PAYMENT_MODES = ("Cash", "UPI", "Card")

# Default category-specific tax rules as a tuple of tuples:
# (category_name, tax_rate_percent, description)
DEFAULT_TAX_RULES = (
    ("Grocery", 5.0, "Essential food and daily grocery items"),
    ("Clothing", 8.0, "Apparel, garments, and footwear"),
    ("Electronics", 18.0, "Consumer electronics and accessories"),
    ("Stationery", 5.0, "Books, pens, paper, and office supplies"),
    ("Household", 12.0, "Home care, kitchenware, and cleaning supplies"),
)

# Default threshold-based discount rules as a list of tuples:
# (min_amount, max_amount, discount_percent, rule_label)
# max_amount = None means "and above" (no upper bound).
DEFAULT_DISCOUNT_RULES = [
    (0.0, 999.99, 0.0, "Below ₹1,000 (No Discount)"),
    (1000.0, 2499.99, 5.0, "₹1,000 – ₹2,499 (5% Off)"),
    (2500.0, 4999.99, 10.0, "₹2,500 – ₹4,999 (10% Off)"),
    (5000.0, None, 15.0, "₹5,000 and above (15% Off)"),
]

# Default store and concession limit settings
DEFAULT_SETTINGS = {
    "store_name": "NovaMart Retail Superstore",
    "store_address": "42 Commerce Avenue, Bengaluru - 560001",
    "store_phone": "+91 80 4123 7890",
    "store_gstin": "29AABCN1234F1Z5",
    "max_concession_limit": 1000.0,
}


def format_inr(amount):
    """Format a numeric amount as Indian Rupees (₹) with 2 decimal places."""
    value = round(float(amount), 2)
    return f"₹{value:,.2f}"


def generate_invoice_number(sequence_number, invoice_date=None):
    """
    Generate a unique formatted invoice number using string operations.
    Example: INV-20261125-0001
    """
    if invoice_date is None:
        date_part = datetime.now().strftime("%Y%m%d")
    elif isinstance(invoice_date, str):
        date_part = invoice_date.replace("-", "")[:8]
    else:
        date_part = invoice_date.strftime("%Y%m%d")

    seq_str = str(int(sequence_number)).zfill(4)
    return f"INV-{date_part}-{seq_str}"


def validate_product_data(product_name, product_code, category, unit_price, available_stock):
    """
    Validate product input fields on the server side.
    Returns a tuple: (is_valid, error_messages_list, cleaned_dict)
    """
    errors = []

    name_clean = str(product_name or "").strip()
    code_clean = str(product_code or "").strip().upper()
    category_clean = str(category or "").strip()

    if len(name_clean) < 2:
        errors.append("Product name must be at least 2 characters long.")
    if len(code_clean) < 2 or " " in code_clean:
        errors.append("Product code must be at least 2 characters with no spaces (e.g., GRO-101).")
    if category_clean not in CATEGORIES:
        errors.append(f"Category must be one of: {', '.join(CATEGORIES)}.")

    try:
        price_val = round(float(unit_price), 2)
        if price_val <= 0:
            errors.append("Unit price must be greater than ₹0.00.")
    except (TypeError, ValueError):
        price_val = 0.0
        errors.append("Unit price must be a valid number.")

    try:
        stock_float = float(available_stock)
        if not stock_float.is_integer():
            errors.append("Available stock must be a whole integer.")
        stock_val = int(stock_float)
        if stock_val < 0:
            errors.append("Available stock cannot be negative.")
    except (TypeError, ValueError):
        stock_val = 0
        errors.append("Available stock must be a valid whole number.")

    cleaned = {
        "product_name": name_clean,
        "product_code": code_clean,
        "category": category_clean,
        "unit_price": price_val,
        "available_stock": stock_val,
    }
    return (len(errors) == 0, errors, cleaned)


def validate_quantity(quantity, available_stock):
    """
    Validate requested cart quantity against positive bounds and available stock.
    Returns (is_valid, error_message, parsed_quantity).
    """
    try:
        qty_float = float(quantity)
        if not qty_float.is_integer():
            return (False, "Quantity must be a whole number.", 0)
        qty = int(qty_float)
    except (TypeError, ValueError):
        return (False, "Quantity must be a valid integer.", 0)

    if qty <= 0:
        return (False, "Quantity must be at least 1.", 0)
    if qty > int(available_stock):
        return (False, f"Requested quantity ({qty}) exceeds available stock ({int(available_stock)}).", 0)

    return (True, "", qty)


def validate_tax_rate(rate):
    """Validate a category tax percentage (0% to 100%)."""
    try:
        val = round(float(rate), 2)
    except (TypeError, ValueError):
        return (False, "Tax rate must be a valid number.", 0.0)

    if val < 0 or val > 100:
        return (False, "Tax rate must be between 0% and 100%.", val)
    return (True, "", val)


def validate_discount_rule(min_amount, max_amount, discount_percent):
    """Validate a threshold discount tier and percentage."""
    errors = []
    try:
        min_val = round(float(min_amount), 2)
        if min_val < 0:
            errors.append("Minimum subtotal cannot be negative.")
    except (TypeError, ValueError):
        min_val = 0.0
        errors.append("Minimum subtotal must be a valid number.")

    if max_amount is None or str(max_amount).strip() == "":
        max_val = None
    else:
        try:
            max_val = round(float(max_amount), 2)
            if max_val < min_val:
                errors.append("Maximum subtotal cannot be less than minimum subtotal.")
        except (TypeError, ValueError):
            max_val = None
            errors.append("Maximum subtotal must be a valid number or left blank.")

    try:
        pct_val = round(float(discount_percent), 2)
        if pct_val < 0 or pct_val > 100:
            errors.append("Discount percentage must be between 0% and 100%.")
    except (TypeError, ValueError):
        pct_val = 0.0
        errors.append("Discount percentage must be a valid number.")

    return (len(errors) == 0, errors, (min_val, max_val, pct_val))


def calculate_line_subtotal(unit_price, quantity):
    """Calculate subtotal for a single product line item."""
    if float(unit_price) < 0 or int(quantity) < 0:
        raise ValueError("Unit price and quantity cannot be negative.")
    return round(float(unit_price) * int(quantity), 2)


def calculate_threshold_discount(subtotal, discount_rules):
    """
    Identify the applicable threshold discount rule and calculate the discount.

    Parameters:
        subtotal (float): Eligible purchase subtotal before discount.
        discount_rules (list of tuples): Each tuple contains
            (min_amount, max_amount, discount_percent[, label]).

    Returns:
        tuple: (discount_percent, discount_amount)
    """
    purchase_subtotal = round(float(subtotal), 2)
    if purchase_subtotal <= 0 or not discount_rules:
        return (0.0, 0.0)

    # Sort rules by minimum threshold ascending using tuple indexing
    sorted_rules = sorted(discount_rules, key=lambda rule: float(rule[0]))

    applied_percent = 0.0
    for rule in sorted_rules:
        # Tuple unpacking (handles 3-tuples or 4-tuples)
        min_amt = float(rule[0])
        max_amt = float(rule[1]) if rule[1] is not None else None
        pct = float(rule[2])

        if max_amt is None:
            if purchase_subtotal >= min_amt:
                applied_percent = pct
        else:
            if min_amt <= purchase_subtotal <= max_amt:
                applied_percent = pct
                break
            elif purchase_subtotal > max_amt:
                # Keep best matched floor if there is a fractional gap between rules
                applied_percent = pct

    discount_amount = round(purchase_subtotal * (applied_percent / 100.0), 2)
    return (round(applied_percent, 2), discount_amount)


def apply_maximum_concession(calculated_discount, max_concession_limit):
    """
    Enforce the maximum discount concession limit per invoice.

    Actual Discount = min(Calculated Threshold Discount, Maximum Discount Limit)
    Returns tuple: (final_discount, cap_applied_bool)
    """
    raw_discount = max(0.0, round(float(calculated_discount), 2))
    limit = max(0.0, round(float(max_concession_limit), 2))

    if raw_discount > limit:
        return (limit, True)
    return (raw_discount, False)


def get_next_discount_nudge(eligible_subtotal, discount_rules):
    """
    Calculate progress toward the next higher threshold discount tier.
    Uses loops and tuple unpacking to guide customers/cashiers in real time.
    """
    subtotal = max(0.0, round(float(eligible_subtotal), 2))
    if not discount_rules:
        return {
            "has_next": False,
            "next_percent": 0.0,
            "amount_needed": 0.0,
            "progress_percent": 100.0,
            "message": "No threshold discount tiers configured.",
        }

    sorted_rules = sorted(discount_rules, key=lambda r: float(r[0]))
    current_pct, _ = calculate_threshold_discount(subtotal, sorted_rules)

    for rule in sorted_rules:
        min_amt = float(rule[0])
        pct = float(rule[2])
        if min_amt > subtotal and pct > current_pct:
            needed = round(min_amt - subtotal, 2)
            progress = round(min(100.0, (subtotal / min_amt) * 100.0), 1) if min_amt > 0 else 100.0
            return {
                "has_next": True,
                "next_percent": pct,
                "amount_needed": needed,
                "progress_percent": progress,
                "message": f"Add {format_inr(needed)} more in eligible items to unlock {pct:.0f}% discount!",
            }

    return {
        "has_next": False,
        "next_percent": current_pct,
        "amount_needed": 0.0,
        "progress_percent": 100.0,
        "message": f"Highest discount tier unlocked ({current_pct:.0f}% Off)!",
    }


def calculate_cash_change(final_payable, payment_mode, cash_tendered_raw):
    """
    Validate payment mode and compute change returned for Cash transactions.
    Returns (is_valid, error_message, tendered_amount, change_due).
    """
    mode = str(payment_mode or "Cash").strip()
    if mode not in PAYMENT_MODES:
        return (False, f"Payment mode must be one of: {', '.join(PAYMENT_MODES)}.", 0.0, 0.0)

    payable = max(0.0, round(float(final_payable), 2))
    if mode != "Cash":
        return (True, "", payable, 0.0)

    raw_str = str(cash_tendered_raw or "").strip()
    if raw_str == "":
        # Exact cash assumed if cashier leaves cash tendered blank
        return (True, "", payable, 0.0)

    try:
        tendered = round(float(raw_str), 2)
    except (TypeError, ValueError):
        return (False, "Cash tendered must be a valid numeric amount.", 0.0, 0.0)

    if tendered < payable:
        return (
            False,
            f"Cash tendered ({format_inr(tendered)}) is less than Final Payable ({format_inr(payable)}).",
            0.0,
            0.0,
        )

    change_due = round(tendered - payable, 2)
    return (True, "", tendered, change_due)


def calculate_invoice(cart_items, tax_rules_map, discount_rules, max_concession_limit):
    """
    Perform complete end-to-end retail bill calculation on the backend.

    Sequence:
    1. Calculate each product's line subtotal.
    2. Calculate total purchase subtotal and discount-eligible subtotal.
    3. Determine applicable threshold discount via calculate_threshold_discount().
    4. Enforce maximum concession limit.
    5. Allocate discount proportionally across eligible line items to compute taxable amount.
    6. Calculate category-specific taxes per item and aggregate by category.
    7. Calculate Final Payable = Product Subtotal - Discount Applied + Category Taxes.

    Returns a dictionary containing summary figures, nested lists of line items,
    and category-wise tax breakdown tuples.
    """
    if not cart_items:
        return {
            "line_items": [],
            "nested_line_items": [],
            "category_summary": [],
            "total_items_count": 0,
            "total_units": 0,
            "purchase_subtotal": 0.0,
            "eligible_subtotal": 0.0,
            "discount_percent": 0.0,
            "eligible_discount": 0.0,
            "max_concession_limit": round(float(max_concession_limit), 2),
            "final_discount": 0.0,
            "concession_capped": False,
            "taxable_amount": 0.0,
            "total_tax": 0.0,
            "final_payable": 0.0,
            "receipt_pattern": "",
        }

    # Step 1 & 2: Compute line subtotals and overall/eligible subtotals
    prepared_items = []
    purchase_subtotal = 0.0
    eligible_subtotal = 0.0
    total_units = 0

    for item in cart_items:
        unit_price = round(float(item["unit_price"]), 2)
        quantity = int(item["quantity"])
        if unit_price < 0 or quantity <= 0:
            raise ValueError("Product price must be non-negative and quantity must be positive.")

        line_sub = calculate_line_subtotal(unit_price, quantity)
        category = str(item["category"])
        tax_rate = round(float(tax_rules_map.get(category, 0.0)), 2)
        if tax_rate < 0 or tax_rate > 100:
            raise ValueError(f"Invalid tax rate for category {category}.")

        is_eligible = bool(item.get("discount_eligible", True))

        purchase_subtotal += line_sub
        if is_eligible:
            eligible_subtotal += line_sub
        total_units += quantity

        prepared_items.append({
            "product_id": int(item["product_id"]),
            "product_code": str(item["product_code"]),
            "product_name": str(item["product_name"]),
            "category": category,
            "unit_price": unit_price,
            "quantity": quantity,
            "line_subtotal": line_sub,
            "discount_eligible": is_eligible,
            "tax_rate": tax_rate,
        })

    purchase_subtotal = round(purchase_subtotal, 2)
    eligible_subtotal = round(eligible_subtotal, 2)

    # Step 3: Threshold discount based on eligible subtotal
    discount_percent, eligible_discount = calculate_threshold_discount(
        eligible_subtotal, discount_rules
    )

    # Step 4: Enforce maximum concession limit
    final_discount, concession_capped = apply_maximum_concession(
        eligible_discount, max_concession_limit
    )

    # Step 5 & 6: Allocate discount across eligible items & compute category-specific tax
    eligible_indices = [idx for idx, row in enumerate(prepared_items) if row["discount_eligible"]]
    allocated_total = 0.0

    for pos, idx in enumerate(eligible_indices):
        row = prepared_items[idx]
        if final_discount <= 0 or eligible_subtotal <= 0:
            item_discount = 0.0
        elif pos == len(eligible_indices) - 1:
            # Assign remaining paise to final eligible item so sum matches exactly
            item_discount = round(final_discount - allocated_total, 2)
        else:
            share_ratio = row["line_subtotal"] / eligible_subtotal
            item_discount = round(final_discount * share_ratio, 2)
            allocated_total += item_discount

        row["discount_amount"] = max(0.0, item_discount)

    # Non-eligible items receive zero discount
    for row in prepared_items:
        if "discount_amount" not in row:
            row["discount_amount"] = 0.0

    # Calculate item taxable amount, category tax, and line total
    nested_line_items = []  # Syllabus concept: Nested Lists
    category_buckets = {}
    total_tax = 0.0

    for row in prepared_items:
        item_taxable = round(row["line_subtotal"] - row["discount_amount"], 2)
        item_tax = round(item_taxable * (row["tax_rate"] / 100.0), 2)
        line_total = round(item_taxable + item_tax, 2)

        row["taxable_amount"] = item_taxable
        row["tax_amount"] = item_tax
        row["line_total"] = line_total
        total_tax += item_tax

        # Nested list representation:
        # [code, name, category, qty, unit_price, line_subtotal, discount, tax_rate, tax_amount, line_total]
        nested_line_items.append([
            row["product_code"],
            row["product_name"],
            row["category"],
            row["quantity"],
            row["unit_price"],
            row["line_subtotal"],
            row["discount_amount"],
            row["tax_rate"],
            row["tax_amount"],
            row["line_total"],
        ])

        cat = row["category"]
        if cat not in category_buckets:
            category_buckets[cat] = {
                "category": cat,
                "tax_rate": row["tax_rate"],
                "subtotal": 0.0,
                "discount_amount": 0.0,
                "taxable_amount": 0.0,
                "tax_amount": 0.0,
                "total_with_tax": 0.0,
            }
        bucket = category_buckets[cat]
        bucket["subtotal"] = round(bucket["subtotal"] + row["line_subtotal"], 2)
        bucket["discount_amount"] = round(bucket["discount_amount"] + row["discount_amount"], 2)
        bucket["taxable_amount"] = round(bucket["taxable_amount"] + item_taxable, 2)
        bucket["tax_amount"] = round(bucket["tax_amount"] + item_tax, 2)
        bucket["total_with_tax"] = round(bucket["total_with_tax"] + line_total, 2)

    total_tax = round(total_tax, 2)
    taxable_amount = round(purchase_subtotal - final_discount, 2)

    # Step 7: Final Payable = Product Subtotal - Discount Applied + Category Taxes
    final_payable = max(0.0, round(purchase_subtotal - final_discount + total_tax, 2))

    # Convert category summary into sorted list of tuples for clean reporting
    category_summary = []
    for cat_name in sorted(category_buckets.keys()):
        b = category_buckets[cat_name]
        category_summary.append((
            b["category"],
            b["tax_rate"],
            b["subtotal"],
            b["discount_amount"],
            b["taxable_amount"],
            b["tax_amount"],
            b["total_with_tax"],
        ))

    discount_nudge = get_next_discount_nudge(eligible_subtotal, discount_rules)

    receipt_pattern = generate_receipt_pattern(
        nested_line_items,
        purchase_subtotal,
        discount_percent,
        final_discount,
        total_tax,
        final_payable,
    )

    return {
        "line_items": prepared_items,
        "nested_line_items": nested_line_items,
        "category_summary": category_summary,
        "total_items_count": len(prepared_items),
        "total_units": total_units,
        "purchase_subtotal": purchase_subtotal,
        "eligible_subtotal": eligible_subtotal,
        "discount_percent": discount_percent,
        "eligible_discount": eligible_discount,
        "max_concession_limit": round(float(max_concession_limit), 2),
        "final_discount": final_discount,
        "concession_capped": concession_capped,
        "taxable_amount": taxable_amount,
        "total_tax": total_tax,
        "final_payable": final_payable,
        "discount_nudge": discount_nudge,
        "receipt_pattern": receipt_pattern,
    }


def generate_receipt_pattern(
    nested_line_items,
    subtotal,
    discount_percent,
    discount_amount,
    total_tax,
    final_payable,
):
    """
    Demonstrate Python string operations and pattern generation using loops
    and string multiplication to format a clean console/text invoice receipt.
    """
    width = 62
    border = "=" * width
    divider = "-" * width
    lines = [
        border,
        "SMART RETAIL BILLING SUMMARY".center(width),
        border,
        f"{'Item':<24}{'Qty':>5}{'Sub(₹)':>11}{'Tax(₹)':>10}{'Net(₹)':>12}",
        divider,
    ]

    for row in nested_line_items:
        # Unpack nested list row
        _code, name, _cat, qty, _price, line_sub, _disc, _rate, tax_amt, line_net = row
        short_name = name[:22] + ".." if len(name) > 24 else name
        lines.append(
            f"{short_name:<24}{qty:>5}{line_sub:>11.2f}{tax_amt:>10.2f}{line_net:>12.2f}"
        )

    lines.extend([
        divider,
        f"{'Purchase Subtotal:':<40}{subtotal:>22.2f}",
        f"{f'Discount Applied ({discount_percent:.1f}%):':<40}{-discount_amount:>22.2f}",
        f"{'Category Taxes:':<40}{total_tax:>22.2f}",
        border,
        f"{'FINAL PAYABLE (INR):':<40}{final_payable:>22.2f}",
        border,
    ])
    return "\n".join(lines)
