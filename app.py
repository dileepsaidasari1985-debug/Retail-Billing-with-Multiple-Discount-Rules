"""
Smart Retail Billing and Discount Management System (Case Study #7)
--------------------------------------------------------------------
Main Flask web application providing:
- Live SQLite-backed Dashboard
- Product Catalog Management (CRUD, search, filter, sort, stock validation)
- Shopping Cart & Billing Counter (multi-item POS, live backend calculations)
- Category-Specific Tax Engine (configurable per category)
- Threshold-Based Discount Engine & Maximum Concession Enforcement
- Itemized Invoice Generation (print-friendly + CSV export, duplicate-safe)
- Billing History & Sales/Discount Reports (with built-in csv exports)
"""

import csv
import io
import os
import secrets

from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from billing_logic import (
    CATEGORIES,
    PAYMENT_MODES,
    calculate_cash_change,
    calculate_invoice,
    format_inr,
    validate_discount_rule,
    validate_product_data,
    validate_quantity,
    validate_tax_rate,
)
from database import (
    DEFAULT_DB_PATH,
    add_discount_rule,
    add_product,
    count_missing_sample_products,
    create_invoice_from_cart,
    delete_discount_rule,
    delete_product,
    get_billing_settings,
    get_dashboard_and_report_stats,
    get_discount_rules,
    get_discount_rules_tuples,
    get_invoice_by_id,
    get_invoices,
    get_low_stock_products,
    get_product_by_id,
    get_products,
    get_tax_rules,
    get_tax_rules_map,
    init_db,
    load_sample_data,
    reset_discount_rules,
    reset_tax_rules,
    restock_product,
    update_billing_settings,
    update_discount_rule,
    update_product,
    update_tax_rule,
)


def create_app(db_path=None, seed_if_empty=True):
    """Create and configure the Flask application instance."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )

    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
    app.config["DB_PATH"] = db_path or DEFAULT_DB_PATH
    app.config["SEED_IF_EMPTY"] = seed_if_empty

    init_db(app.config["DB_PATH"], seed_if_empty=seed_if_empty)

    @app.before_request
    def ensure_db_ready():
        """Ensure SQLite database file exists before handling requests."""
        if not os.path.exists(app.config["DB_PATH"]):
            init_db(app.config["DB_PATH"], seed_if_empty=app.config["SEED_IF_EMPTY"])

    def get_csrf_token():
        """Return a stable CSRF token stored in session and mirrored in cookie."""
        cached = getattr(g, "_csrf_token", None)
        if cached:
            return cached
        token = session.get("csrf_token") or request.cookies.get("csrf_cookie")
        if not token:
            token = secrets.token_hex(24)
        session["csrf_token"] = token
        g._csrf_token = token
        return token

    @app.after_request
    def set_csrf_cookie(response):
        """Sync CSRF cookie for reliable verification across requests."""
        token = getattr(g, "_csrf_token", None) or session.get("csrf_token")
        if token and request.cookies.get("csrf_cookie") != token:
            response.set_cookie("csrf_cookie", token, httponly=True, samesite="Lax")
        return response

    def verify_csrf():
        """Validate submitted CSRF token on state-changing POST requests."""
        submitted = request.form.get("csrf_token", "")
        session_token = session.get("csrf_token", "")
        cookie_token = request.cookies.get("csrf_cookie", "")
        if not submitted:
            abort(403, description="Missing CSRF token.")
        valid_session = session_token and secrets.compare_digest(submitted, session_token)
        valid_cookie = cookie_token and secrets.compare_digest(submitted, cookie_token)
        if not (valid_session or valid_cookie):
            abort(403, description="Invalid CSRF token.")

    def get_session_cart():
        """Return cart dict {str(product_id): int(qty)} from Flask session."""
        raw_cart = session.get("cart", {})
        cleaned = {}
        for pid_str, qty in raw_cart.items():
            try:
                pid_int = int(pid_str)
                qty_int = int(qty)
                if qty_int > 0:
                    cleaned[str(pid_int)] = qty_int
            except (TypeError, ValueError):
                continue
        return cleaned

    def save_session_cart(cart_dict):
        """Persist cart dict back to Flask session."""
        session["cart"] = cart_dict
        session.modified = True

    def build_cart_computation(db_file):
        """
        Resolve session cart items against live SQLite product rows and run
        the full Python billing engine on the backend.
        """
        cart_map = get_session_cart()
        resolved_items = []
        valid_cart = {}
        adjusted_notices = []

        for pid_str, requested_qty in cart_map.items():
            prod = get_product_by_id(db_file, int(pid_str))
            if prod is None or prod["available_stock"] <= 0:
                adjusted_notices.append(f"Removed unavailable product (ID {pid_str}) from cart.")
                continue

            qty = min(int(requested_qty), int(prod["available_stock"]))
            if qty < int(requested_qty):
                adjusted_notices.append(
                    f"Adjusted quantity of {prod['product_name']} to available stock ({qty})."
                )

            valid_cart[pid_str] = qty
            resolved_items.append({
                "product_id": prod["id"],
                "product_code": prod["product_code"],
                "product_name": prod["product_name"],
                "category": prod["category"],
                "unit_price": float(prod["unit_price"]),
                "available_stock": int(prod["available_stock"]),
                "quantity": qty,
                "discount_eligible": bool(prod["discount_eligible"]),
            })

        if valid_cart != cart_map:
            save_session_cart(valid_cart)

        tax_map = get_tax_rules_map(db_file)
        disc_rules = get_discount_rules_tuples(db_file)
        settings = get_billing_settings(db_file)
        bill_summary = calculate_invoice(
            resolved_items,
            tax_map,
            disc_rules,
            float(settings["max_concession_limit"]),
        )

        # Attach stock info onto computed line items for UI +/- limits
        stock_lookup = {item["product_id"]: item["available_stock"] for item in resolved_items}
        for row in bill_summary["line_items"]:
            row["available_stock"] = stock_lookup.get(row["product_id"], row["quantity"])

        return bill_summary, adjusted_notices

    @app.context_processor
    def inject_globals():
        """Expose shared store settings, CSRF token, cart count, and helpers to templates."""
        db_file = app.config["DB_PATH"]
        settings = get_billing_settings(db_file)
        cart_map = get_session_cart()
        return {
            "store_settings": settings,
            "csrf_token": get_csrf_token,
            "cart_units_count": sum(cart_map.values()),
            "categories": CATEGORIES,
            "payment_modes": PAYMENT_MODES,
            "format_inr": format_inr,
        }

    # -----------------------------------------------------------------------
    # A. Dashboard
    # -----------------------------------------------------------------------
    @app.route("/")
    def dashboard():
        db_file = app.config["DB_PATH"]
        stats = get_dashboard_and_report_stats(db_file)
        missing_samples = count_missing_sample_products(db_file)
        discount_rules = get_discount_rules(db_file)
        tax_rules = get_tax_rules(db_file)
        low_stock_products = get_low_stock_products(db_file, threshold=10)
        return render_template(
            "dashboard.html",
            active_page="dashboard",
            stats=stats,
            missing_samples=missing_samples,
            discount_rules=discount_rules,
            tax_rules=tax_rules,
            low_stock_products=low_stock_products,
        )

    @app.route("/load-sample-data", methods=["POST"])
    def load_samples_route():
        verify_csrf()
        db_file = app.config["DB_PATH"]
        added_prods, added_invs = load_sample_data(db_file, include_invoices=True)
        if added_prods == 0 and added_invs == 0:
            flash("All sample products and sample records are already loaded.", "info")
        else:
            flash(
                f"Loaded {added_prods} sample product(s) and {added_invs} sample invoice(s) without duplicates.",
                "success",
            )
        next_url = request.form.get("next") or url_for("dashboard")
        return redirect(next_url)

    # -----------------------------------------------------------------------
    # B. Product Management
    # -----------------------------------------------------------------------
    @app.route("/products")
    def products_page():
        db_file = app.config["DB_PATH"]
        search = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        sort_by = request.args.get("sort", "name_asc").strip()

        products = get_products(db_file, search=search, category=category, sort_by=sort_by)
        tax_map = get_tax_rules_map(db_file)
        missing_samples = count_missing_sample_products(db_file)

        return render_template(
            "products.html",
            active_page="products",
            products=products,
            tax_map=tax_map,
            search=search,
            selected_category=category,
            sort_by=sort_by,
            missing_samples=missing_samples,
        )

    @app.route("/products/add", methods=["GET", "POST"])
    def add_product_page():
        db_file = app.config["DB_PATH"]
        form_data = {
            "product_code": "",
            "product_name": "",
            "category": "Grocery",
            "unit_price": "",
            "available_stock": "",
            "discount_eligible": True,
        }

        if request.method == "POST":
            verify_csrf()
            form_data = {
                "product_code": request.form.get("product_code", ""),
                "product_name": request.form.get("product_name", ""),
                "category": request.form.get("category", ""),
                "unit_price": request.form.get("unit_price", ""),
                "available_stock": request.form.get("available_stock", ""),
                "discount_eligible": request.form.get("discount_eligible") == "on",
            }
            valid, errors, cleaned = validate_product_data(
                form_data["product_name"],
                form_data["product_code"],
                form_data["category"],
                form_data["unit_price"],
                form_data["available_stock"],
            )
            if not valid:
                for err in errors:
                    flash(err, "error")
            else:
                ok, msg, _pid = add_product(
                    db_file,
                    cleaned["product_code"],
                    cleaned["product_name"],
                    cleaned["category"],
                    cleaned["unit_price"],
                    cleaned["available_stock"],
                    form_data["discount_eligible"],
                )
                if ok:
                    flash(msg, "success")
                    return redirect(url_for("products_page"))
                flash(msg, "error")

        tax_map = get_tax_rules_map(db_file)
        return render_template(
            "add_product.html",
            active_page="add_product",
            mode="add",
            product=None,
            form_data=form_data,
            tax_map=tax_map,
        )

    @app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
    def edit_product_page(product_id):
        db_file = app.config["DB_PATH"]
        product = get_product_by_id(db_file, product_id)
        if product is None:
            abort(404)

        form_data = {
            "product_code": product["product_code"],
            "product_name": product["product_name"],
            "category": product["category"],
            "unit_price": f"{product['unit_price']:.2f}",
            "available_stock": str(product["available_stock"]),
            "discount_eligible": bool(product["discount_eligible"]),
        }

        if request.method == "POST":
            verify_csrf()
            form_data = {
                "product_code": request.form.get("product_code", ""),
                "product_name": request.form.get("product_name", ""),
                "category": request.form.get("category", ""),
                "unit_price": request.form.get("unit_price", ""),
                "available_stock": request.form.get("available_stock", ""),
                "discount_eligible": request.form.get("discount_eligible") == "on",
            }
            valid, errors, cleaned = validate_product_data(
                form_data["product_name"],
                form_data["product_code"],
                form_data["category"],
                form_data["unit_price"],
                form_data["available_stock"],
            )
            if not valid:
                for err in errors:
                    flash(err, "error")
            else:
                ok, msg = update_product(
                    db_file,
                    product_id,
                    cleaned["product_code"],
                    cleaned["product_name"],
                    cleaned["category"],
                    cleaned["unit_price"],
                    cleaned["available_stock"],
                    form_data["discount_eligible"],
                )
                if ok:
                    flash(msg, "success")
                    return redirect(url_for("products_page"))
                flash(msg, "error")

        tax_map = get_tax_rules_map(db_file)
        return render_template(
            "add_product.html",
            active_page="products",
            mode="edit",
            product=product,
            form_data=form_data,
            tax_map=tax_map,
        )

    @app.route("/products/<int:product_id>/delete", methods=["POST"])
    def delete_product_route(product_id):
        verify_csrf()
        db_file = app.config["DB_PATH"]
        product = get_product_by_id(db_file, product_id)
        if product is None:
            flash("Product was not found or already deleted.", "error")
            return redirect(url_for("products_page"))

        deleted = delete_product(db_file, product_id)
        if deleted:
            cart = get_session_cart()
            if str(product_id) in cart:
                del cart[str(product_id)]
                save_session_cart(cart)
            flash(f"Deleted '{product['product_name']}' ({product['product_code']}).", "success")
        else:
            flash("Unable to delete product.", "error")
        return redirect(url_for("products_page"))

    @app.route("/products/<int:product_id>/restock", methods=["POST"])
    def restock_product_route(product_id):
        verify_csrf()
        db_file = app.config["DB_PATH"]
        try:
            add_units = int(request.form.get("add_units", 10))
        except (TypeError, ValueError):
            add_units = 10
        ok, msg = restock_product(db_file, product_id, add_units)
        flash(msg, "success" if ok else "error")
        next_url = request.form.get("next") or url_for("products_page")
        return redirect(next_url)

    # -----------------------------------------------------------------------
    # C. Shopping Cart & Billing Counter
    # -----------------------------------------------------------------------
    @app.route("/billing")
    def billing_counter_page():
        db_file = app.config["DB_PATH"]
        search = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()

        products = get_products(db_file, search=search, category=category, sort_by="name_asc")
        tax_map = get_tax_rules_map(db_file)
        discount_rules = get_discount_rules(db_file)
        cart_bill, notices = build_cart_computation(db_file)
        for note in notices:
            flash(note, "info")

        # Generate a fresh one-time checkout nonce to guard against duplicate submissions
        if "checkout_nonce" not in session:
            session["checkout_nonce"] = secrets.token_hex(16)

        cart_quantities = {
            item["product_id"]: item["quantity"] for item in cart_bill["line_items"]
        }

        return render_template(
            "billing_counter.html",
            active_page="billing",
            products=products,
            tax_map=tax_map,
            discount_rules=discount_rules,
            bill=cart_bill,
            cart_quantities=cart_quantities,
            search=search,
            selected_category=category,
            checkout_nonce=session["checkout_nonce"],
        )

    @app.route("/billing/cart/add", methods=["POST"])
    def cart_add_route():
        verify_csrf()
        db_file = app.config["DB_PATH"]
        try:
            product_id = int(request.form.get("product_id", 0))
        except (TypeError, ValueError):
            flash("Invalid product selected.", "error")
            return redirect(url_for("billing_counter_page"))

        product = get_product_by_id(db_file, product_id)
        if product is None:
            flash("Selected product does not exist.", "error")
            return redirect(url_for("billing_counter_page"))

        if product["available_stock"] <= 0:
            flash(f"'{product['product_name']}' is currently out of stock.", "error")
            return redirect(url_for("billing_counter_page"))

        cart = get_session_cart()
        existing_qty = cart.get(str(product_id), 0)
        add_raw = request.form.get("quantity", "1")
        valid_add, err_msg, add_qty = validate_quantity(add_raw, product["available_stock"])
        if not valid_add:
            flash(err_msg, "error")
            return redirect(url_for("billing_counter_page"))

        new_total_qty = existing_qty + add_qty
        if new_total_qty > product["available_stock"]:
            flash(
                f"Cannot add {add_qty} more of '{product['product_name']}'. "
                f"Cart already has {existing_qty} and stock is {product['available_stock']}.",
                "error",
            )
            return redirect(url_for("billing_counter_page"))

        cart[str(product_id)] = new_total_qty
        save_session_cart(cart)
        flash(f"Added {add_qty} × {product['product_name']} to cart.", "success")
        return redirect(url_for("billing_counter_page", q=request.form.get("q", ""), category=request.form.get("category", "")))

    @app.route("/billing/cart/update", methods=["POST"])
    def cart_update_route():
        verify_csrf()
        db_file = app.config["DB_PATH"]
        try:
            product_id = int(request.form.get("product_id", 0))
        except (TypeError, ValueError):
            flash("Invalid cart item.", "error")
            return redirect(url_for("billing_counter_page"))

        product = get_product_by_id(db_file, product_id)
        if product is None:
            flash("Product not found.", "error")
            return redirect(url_for("billing_counter_page"))

        cart = get_session_cart()
        pid_key = str(product_id)
        current_qty = cart.get(pid_key, 0)
        action = request.form.get("action", "set")

        if action == "inc":
            target_qty = current_qty + 1
        elif action == "dec":
            target_qty = current_qty - 1
        else:
            try:
                target_qty = int(float(request.form.get("quantity", 0)))
            except (TypeError, ValueError):
                flash("Quantity must be a valid whole number.", "error")
                return redirect(url_for("billing_counter_page"))

        if target_qty <= 0:
            if pid_key in cart:
                del cart[pid_key]
                save_session_cart(cart)
                flash(f"Removed '{product['product_name']}' from cart.", "info")
            return redirect(url_for("billing_counter_page"))

        valid, err_msg, clean_qty = validate_quantity(target_qty, product["available_stock"])
        if not valid:
            flash(err_msg, "error")
            return redirect(url_for("billing_counter_page"))

        cart[pid_key] = clean_qty
        save_session_cart(cart)
        return redirect(url_for("billing_counter_page"))

    @app.route("/billing/cart/remove", methods=["POST"])
    def cart_remove_route():
        verify_csrf()
        pid_key = str(request.form.get("product_id", "")).strip()
        cart = get_session_cart()
        if pid_key in cart:
            del cart[pid_key]
            save_session_cart(cart)
            flash("Item removed from cart.", "info")
        return redirect(url_for("billing_counter_page"))

    @app.route("/billing/cart/clear", methods=["POST"])
    def cart_clear_route():
        verify_csrf()
        save_session_cart({})
        flash("Shopping cart cleared.", "info")
        return redirect(url_for("billing_counter_page"))

    @app.route("/billing/load-demo-basket", methods=["POST"])
    def load_demo_basket_route():
        verify_csrf()
        db_file = app.config["DB_PATH"]
        preset = request.form.get("preset", "cap_demo")
        presets_map = {
            "tier5_demo": [("GRO-101", 2), ("STA-401", 2)],
            "cap_demo": [("ELE-203", 2), ("CLO-301", 2), ("GRO-102", 1)],
        }
        chosen = presets_map.get(preset, presets_map["cap_demo"])
        products_by_code = {p["product_code"]: p for p in get_products(db_file)}
        new_cart = {}
        loaded_count = 0
        for code, qty in chosen:
            prod = products_by_code.get(code)
            if prod and prod["available_stock"] > 0:
                new_cart[str(prod["id"])] = min(qty, int(prod["available_stock"]))
                loaded_count += 1
        if loaded_count == 0:
            flash("No stock available for demo preset items. Restock products first.", "error")
        else:
            save_session_cart(new_cart)
            flash("Loaded sample POS basket to demonstrate discount & tax rules.", "success")
        return redirect(url_for("billing_counter_page"))

    @app.route("/billing/checkout", methods=["POST"])
    def billing_checkout_route():
        verify_csrf()
        db_file = app.config["DB_PATH"]

        submitted_nonce = request.form.get("checkout_nonce", "")
        expected_nonce = session.get("checkout_nonce", "")
        if not submitted_nonce or not expected_nonce or not secrets.compare_digest(submitted_nonce, expected_nonce):
            flash("This billing request was already processed or expired.", "info")
            return redirect(url_for("billing_counter_page"))

        cart = get_session_cart()
        if not cart:
            flash("Your cart is empty. Add products before generating an invoice.", "error")
            return redirect(url_for("billing_counter_page"))

        cart_bill, _ = build_cart_computation(db_file)
        payment_mode = request.form.get("payment_mode", "Cash").strip()
        cash_raw = request.form.get("cash_tendered", "")
        pay_ok, pay_err, tendered_amt, change_amt = calculate_cash_change(
            cart_bill["final_payable"], payment_mode, cash_raw
        )
        if not pay_ok:
            flash(pay_err, "error")
            return redirect(url_for("billing_counter_page"))

        cart_int_map = {int(k): int(v) for k, v in cart.items()}
        customer_name = request.form.get("customer_name", "").strip() or "Walk-in Customer"

        ok, msg, invoice_id = create_invoice_from_cart(
            db_file,
            cart_int_map,
            customer_name,
            payment_mode=payment_mode,
            cash_tendered=tendered_amt,
            change_due=change_amt,
        )
        if not ok:
            flash(msg, "error")
            return redirect(url_for("billing_counter_page"))

        # Clear cart and consume one-time nonce so refresh never duplicates invoice
        save_session_cart({})
        session.pop("checkout_nonce", None)
        flash(msg, "success")
        return redirect(url_for("invoice_detail_page", invoice_id=invoice_id))

    # -----------------------------------------------------------------------
    # H. Invoice Details & CSV Export
    # -----------------------------------------------------------------------
    @app.route("/invoice/<int:invoice_id>")
    def invoice_detail_page(invoice_id):
        db_file = app.config["DB_PATH"]
        data = get_invoice_by_id(db_file, invoice_id)
        if data is None:
            abort(404)

        inv = data["invoice"]
        items = data["items"]
        nested_rows = [
            [
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
            ]
            for row in items
        ]
        from billing_logic import generate_receipt_pattern

        receipt_pattern = generate_receipt_pattern(
            nested_rows,
            inv["purchase_subtotal"],
            inv["discount_percent"],
            inv["final_discount"],
            inv["total_tax"],
            inv["final_payable"],
        )

        return render_template(
            "invoice.html",
            active_page="billing_history",
            invoice=inv,
            items=items,
            category_summary=data["category_summary"],
            receipt_pattern=receipt_pattern,
        )

    @app.route("/invoice/<int:invoice_id>/csv")
    def invoice_csv_route(invoice_id):
        db_file = app.config["DB_PATH"]
        data = get_invoice_by_id(db_file, invoice_id)
        if data is None:
            abort(404)

        inv = data["invoice"]
        items = data["items"]
        settings = get_billing_settings(db_file)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Store Name", settings["store_name"]])
        writer.writerow(["Store Address", settings["store_address"]])
        writer.writerow(["Invoice Number", inv["invoice_number"]])
        writer.writerow(["Invoice Date & Time", inv["invoice_datetime"]])
        writer.writerow(["Customer Name", inv["customer_name"]])
        writer.writerow(["Payment Mode", inv.get("payment_mode", "Cash")])
        writer.writerow([])
        writer.writerow([
            "Product Code",
            "Product Name",
            "Category",
            "Quantity",
            "Unit Price (INR)",
            "Line Subtotal (INR)",
            "Discount (INR)",
            "Taxable Amount (INR)",
            "Tax Rate (%)",
            "Tax Amount (INR)",
            "Final Line Total (INR)",
        ])
        for row in items:
            writer.writerow([
                row["product_code"],
                row["product_name"],
                row["category"],
                row["quantity"],
                f"{row['unit_price']:.2f}",
                f"{row['line_subtotal']:.2f}",
                f"{row['discount_amount']:.2f}",
                f"{row['taxable_amount']:.2f}",
                f"{row['tax_rate']:.2f}",
                f"{row['tax_amount']:.2f}",
                f"{row['line_total']:.2f}",
            ])
        writer.writerow([])
        writer.writerow(["Purchase Subtotal (INR)", f"{inv['purchase_subtotal']:.2f}"])
        writer.writerow(["Discount Percent (%)", f"{inv['discount_percent']:.2f}"])
        writer.writerow(["Eligible Discount (INR)", f"{inv['eligible_discount']:.2f}"])
        writer.writerow(["Maximum Concession Limit (INR)", f"{inv['max_concession_limit']:.2f}"])
        writer.writerow(["Final Discount Applied (INR)", f"{inv['final_discount']:.2f}"])
        writer.writerow(["Taxable Amount (INR)", f"{inv['taxable_amount']:.2f}"])
        writer.writerow(["Total Category Taxes (INR)", f"{inv['total_tax']:.2f}"])
        writer.writerow(["Final Payable Amount (INR)", f"{inv['final_payable']:.2f}"])

        filename = f"{inv['invoice_number']}.csv"
        return Response(
            "\ufeff" + output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # -----------------------------------------------------------------------
    # I. Billing History
    # -----------------------------------------------------------------------
    @app.route("/history")
    def billing_history_page():
        db_file = app.config["DB_PATH"]
        search = request.args.get("q", "").strip()
        filter_date = request.args.get("date", "").strip()
        sort_by = request.args.get("sort", "newest").strip()

        invoices = get_invoices(db_file, search=search, filter_date=filter_date, sort_by=sort_by)
        return render_template(
            "billing_history.html",
            active_page="billing_history",
            invoices=invoices,
            search=search,
            filter_date=filter_date,
            sort_by=sort_by,
        )

    # -----------------------------------------------------------------------
    # D. Category-Specific Tax Rules
    # -----------------------------------------------------------------------
    @app.route("/tax-rules", methods=["GET", "POST"])
    def tax_rules_page():
        db_file = app.config["DB_PATH"]
        if request.method == "POST":
            verify_csrf()
            action = request.form.get("action", "update")
            if action == "reset":
                reset_tax_rules(db_file)
                flash("Category tax rules restored to academic defaults.", "success")
                return redirect(url_for("tax_rules_page"))

            rules = get_tax_rules(db_file)
            errors = []
            updates = []
            for rule in rules:
                rid = rule["id"]
                rate_raw = request.form.get(f"tax_rate_{rid}", "")
                desc_raw = request.form.get(f"description_{rid}", rule["description"])
                ok, err, rate_val = validate_tax_rate(rate_raw)
                if not ok:
                    errors.append(f"{rule['category']}: {err}")
                else:
                    updates.append((rid, rate_val, desc_raw))

            if errors:
                for err in errors:
                    flash(err, "error")
            else:
                for rid, rate_val, desc_raw in updates:
                    update_tax_rule(db_file, rid, rate_val, desc_raw)
                flash("Category tax rules updated successfully.", "success")
            return redirect(url_for("tax_rules_page"))

        tax_rules = get_tax_rules(db_file)
        return render_template(
            "tax_rules.html",
            active_page="tax_rules",
            tax_rules=tax_rules,
        )

    # -----------------------------------------------------------------------
    # E & F. Threshold Discount Rules & Maximum Concession Limit
    # -----------------------------------------------------------------------
    @app.route("/discount-rules", methods=["GET", "POST"])
    def discount_rules_page():
        db_file = app.config["DB_PATH"]
        if request.method == "POST":
            verify_csrf()
            action = request.form.get("action", "")

            if action == "reset":
                reset_discount_rules(db_file)
                flash("Discount thresholds and maximum concession limit reset to defaults.", "success")
                return redirect(url_for("discount_rules_page"))

            if action == "update_settings":
                store_name = request.form.get("store_name", "")
                store_address = request.form.get("store_address", "")
                store_phone = request.form.get("store_phone", "")
                store_gstin = request.form.get("store_gstin", "")
                limit_raw = request.form.get("max_concession_limit", "")
                try:
                    limit_val = round(float(limit_raw), 2)
                    if limit_val < 0:
                        raise ValueError("Maximum concession limit cannot be negative.")
                    update_billing_settings(
                        db_file, store_name, store_address, store_phone, store_gstin, limit_val
                    )
                    flash("Billing settings and maximum concession limit updated.", "success")
                except (TypeError, ValueError) as exc:
                    flash(f"Invalid maximum concession limit: {exc}", "error")
                return redirect(url_for("discount_rules_page"))

            if action == "add_rule":
                ok, errors, parsed = validate_discount_rule(
                    request.form.get("min_amount", ""),
                    request.form.get("max_amount", ""),
                    request.form.get("discount_percent", ""),
                )
                if not ok:
                    for err in errors:
                        flash(err, "error")
                else:
                    min_val, max_val, pct_val = parsed
                    add_discount_rule(
                        db_file,
                        min_val,
                        max_val,
                        pct_val,
                        request.form.get("rule_label", ""),
                    )
                    flash("New threshold discount rule added.", "success")
                return redirect(url_for("discount_rules_page"))

            if action == "update_rule":
                try:
                    rule_id = int(request.form.get("rule_id", 0))
                except (TypeError, ValueError):
                    flash("Invalid rule ID.", "error")
                    return redirect(url_for("discount_rules_page"))

                ok, errors, parsed = validate_discount_rule(
                    request.form.get("min_amount", ""),
                    request.form.get("max_amount", ""),
                    request.form.get("discount_percent", ""),
                )
                if not ok:
                    for err in errors:
                        flash(err, "error")
                else:
                    min_val, max_val, pct_val = parsed
                    update_discount_rule(
                        db_file,
                        rule_id,
                        min_val,
                        max_val,
                        pct_val,
                        request.form.get("rule_label", ""),
                    )
                    flash("Discount rule updated.", "success")
                return redirect(url_for("discount_rules_page"))

            if action == "delete_rule":
                try:
                    rule_id = int(request.form.get("rule_id", 0))
                    if len(get_discount_rules(db_file)) <= 1:
                        flash("At least one discount rule must remain configured.", "error")
                    else:
                        delete_discount_rule(db_file, rule_id)
                        flash("Discount rule removed.", "success")
                except (TypeError, ValueError):
                    flash("Invalid rule ID.", "error")
                return redirect(url_for("discount_rules_page"))

        discount_rules = get_discount_rules(db_file)
        settings = get_billing_settings(db_file)
        return render_template(
            "discount_rules.html",
            active_page="discount_rules",
            discount_rules=discount_rules,
            settings=settings,
        )

    # -----------------------------------------------------------------------
    # J. Discount and Sales Reports + CSV Downloads
    # -----------------------------------------------------------------------
    @app.route("/reports")
    def reports_page():
        db_file = app.config["DB_PATH"]
        stats = get_dashboard_and_report_stats(db_file)
        invoices = get_invoices(db_file, sort_by="newest")
        return render_template(
            "reports.html",
            active_page="reports",
            stats=stats,
            invoices=invoices,
        )

    @app.route("/reports/csv")
    def reports_csv_route():
        db_file = app.config["DB_PATH"]
        report_type = request.args.get("type", "full").strip().lower()
        stats = get_dashboard_and_report_stats(db_file)
        invoices = get_invoices(db_file, sort_by="newest")

        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "invoices":
            writer.writerow([
                "Invoice Number",
                "Date & Time",
                "Customer Name",
                "Payment Mode",
                "Items",
                "Units",
                "Purchase Subtotal (INR)",
                "Discount %",
                "Eligible Discount (INR)",
                "Final Discount (INR)",
                "Concession Capped",
                "Taxable Amount (INR)",
                "Total Tax (INR)",
                "Final Payable (INR)",
            ])
            for inv in invoices:
                writer.writerow([
                    inv["invoice_number"],
                    inv["invoice_datetime"],
                    inv["customer_name"],
                    inv.get("payment_mode", "Cash"),
                    inv["total_items"],
                    inv["total_units"],
                    f"{inv['purchase_subtotal']:.2f}",
                    f"{inv['discount_percent']:.2f}",
                    f"{inv['eligible_discount']:.2f}",
                    f"{inv['final_discount']:.2f}",
                    "Yes" if inv["concession_capped"] else "No",
                    f"{inv['taxable_amount']:.2f}",
                    f"{inv['total_tax']:.2f}",
                    f"{inv['final_payable']:.2f}",
                ])
            filename = "retail_invoices_report.csv"
        else:
            writer.writerow(["SMART RETAIL BILLING & DISCOUNT REPORT"])
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Total Invoices", stats["total_invoices"]])
            writer.writerow(["Total Products in Catalog", stats["total_products"]])
            writer.writerow(["Total Sales (INR)", f"{stats['total_sales']:.2f}"])
            writer.writerow(["Total Discounts Given (INR)", f"{stats['total_discounts']:.2f}"])
            writer.writerow(["Total Tax Collected (INR)", f"{stats['total_tax']:.2f}"])
            writer.writerow(["Average Invoice Value (INR)", f"{stats['avg_invoice']:.2f}"])
            writer.writerow(["Highest Invoice Value (INR)", f"{stats['highest_invoice']:.2f}"])
            writer.writerow(["Concession-Capped Invoices", stats["capped_invoices"]])
            writer.writerow([
                "Most Frequently Sold Product",
                f"{stats['top_product']['product_name']} ({stats['top_product']['total_qty']} units)"
                if stats["top_product"]
                else "N/A",
            ])
            writer.writerow([])
            writer.writerow(["CATEGORY-WISE SALES & TAX BREAKDOWN"])
            writer.writerow([
                "Category",
                "Invoices",
                "Units Sold",
                "Gross Sales (INR)",
                "Discounts Given (INR)",
                "Tax Collected (INR)",
                "Net Sales (INR)",
            ])
            for cat in stats["category_breakdown"]:
                writer.writerow([
                    cat["category"],
                    cat["invoice_count"],
                    cat["units_sold"],
                    f"{cat['gross_sales']:.2f}",
                    f"{cat['discounts_given']:.2f}",
                    f"{cat['tax_collected']:.2f}",
                    f"{cat['net_sales']:.2f}",
                ])
            writer.writerow([])
            writer.writerow(["INVOICE LOG"])
            writer.writerow([
                "Invoice Number",
                "Date & Time",
                "Customer Name",
                "Subtotal (INR)",
                "Discount (INR)",
                "Tax (INR)",
                "Final Payable (INR)",
            ])
            for inv in invoices:
                writer.writerow([
                    inv["invoice_number"],
                    inv["invoice_datetime"],
                    inv["customer_name"],
                    f"{inv['purchase_subtotal']:.2f}",
                    f"{inv['final_discount']:.2f}",
                    f"{inv['total_tax']:.2f}",
                    f"{inv['final_payable']:.2f}",
                ])
            filename = "retail_sales_discount_report.csv"

        return Response(
            "\ufeff" + output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="127.0.0.1", port=port)
