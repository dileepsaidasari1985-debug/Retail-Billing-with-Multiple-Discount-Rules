# Pseudocode — Smart Retail Billing & Discount System

## 1. Product Selection & Quantity / Stock Validation

```text
FUNCTION validate_and_add_to_cart(cart, product, requested_qty):
    IF requested_qty <= 0 OR requested_qty IS NOT INTEGER THEN
        RETURN ERROR "Quantity must be a positive whole number"
    END IF

    existing_qty <- cart.get(product.id, 0)
    IF (existing_qty + requested_qty) > product.available_stock THEN
        RETURN ERROR "Requested quantity exceeds available stock"
    END IF

    cart[product.id] <- existing_qty + requested_qty
    RETURN SUCCESS
END FUNCTION
```

## 2. Line Subtotal & Purchase Subtotal Calculation

```text
FUNCTION compute_subtotals(cart_items):
    purchase_subtotal <- 0.0
    eligible_subtotal <- 0.0

    FOR EACH item IN cart_items DO
        line_subtotal <- ROUND(item.unit_price * item.quantity, 2)
        item.line_subtotal <- line_subtotal
        purchase_subtotal <- purchase_subtotal + line_subtotal

        IF item.discount_eligible == TRUE THEN
            eligible_subtotal <- eligible_subtotal + line_subtotal
        END IF
    END FOR

    RETURN ROUND(purchase_subtotal, 2), ROUND(eligible_subtotal, 2)
END FUNCTION
```

## 3. Threshold-Based Discount Calculation

```text
FUNCTION calculate_threshold_discount(subtotal, discount_rules):
    IF subtotal <= 0 OR discount_rules IS EMPTY THEN
        RETURN (0.0, 0.0)
    END IF

    SORT discount_rules BY min_amount ASCENDING
    applied_percent <- 0.0

    FOR EACH (min_amt, max_amt, pct, label) IN discount_rules DO
        IF max_amt IS NULL THEN
            IF subtotal >= min_amt THEN
                applied_percent <- pct
            END IF
        ELSE
            IF subtotal >= min_amt AND subtotal <= max_amt THEN
                applied_percent <- pct
                BREAK
            ELSE IF subtotal > max_amt THEN
                applied_percent <- pct
            END IF
        END IF
    END FOR

    discount_amount <- ROUND(subtotal * (applied_percent / 100.0), 2)
    RETURN (applied_percent, discount_amount)
END FUNCTION
```

## 4. Maximum Concession Limit Enforcement

```text
FUNCTION apply_maximum_concession(calculated_discount, max_concession_limit):
    IF calculated_discount > max_concession_limit THEN
        RETURN (max_concession_limit, TRUE)
    ELSE
        RETURN (calculated_discount, FALSE)
    END IF
END FUNCTION
```

## 5. Category-Specific Tax & Final Invoice Generation

```text
FUNCTION generate_final_invoice(cart_items, tax_rules_map, discount_rules, max_limit):
    purchase_subtotal, eligible_subtotal <- compute_subtotals(cart_items)
    discount_pct, eligible_discount <- calculate_threshold_discount(eligible_subtotal, discount_rules)
    final_discount, capped <- apply_maximum_concession(eligible_discount, max_limit)

    total_tax <- 0.0
    FOR EACH item IN cart_items DO
        IF item.discount_eligible == TRUE AND eligible_subtotal > 0 THEN
            item.discount <- ROUND(final_discount * (item.line_subtotal / eligible_subtotal), 2)
        ELSE
            item.discount <- 0.0
        END IF

        item.taxable <- ROUND(item.line_subtotal - item.discount, 2)
        item.tax_rate <- tax_rules_map[item.category]
        item.tax_amount <- ROUND(item.taxable * (item.tax_rate / 100.0), 2)
        item.line_total <- ROUND(item.taxable + item.tax_amount, 2)
        total_tax <- total_tax + item.tax_amount
    END FOR

    taxable_amount <- ROUND(purchase_subtotal - final_discount, 2)
    final_payable <- ROUND(purchase_subtotal - final_discount + total_tax, 2)

    SAVE invoice AND invoice_items TO SQLite
    DEDUCT purchased quantities FROM products.available_stock
    RETURN invoice
END FUNCTION
```
