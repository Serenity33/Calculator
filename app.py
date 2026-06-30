from flask import Flask, render_template, request, redirect, url_for, session, send_file
import io
import csv
from bookkeeping.db import init_db
from bookkeeping import repository as repo

app = Flask(__name__)
app.secret_key = "bookkeeping-secret-key"

CURRENCY = "CA$"


@app.before_request
def setup():
    init_db()


def get_current_business():
    biz_id = session.get("business_id")
    if biz_id:
        return repo.get_business(biz_id)
    return None


# ── Home / business selection ─────────────────────────────────────────────

@app.route("/")
def index():
    businesses = repo.list_businesses()
    if not businesses:
        return render_template("index.html", businesses=[], currency=CURRENCY)
    biz_id = session.get("business_id")
    if biz_id and any(b.id == biz_id for b in businesses):
        return redirect(url_for("dashboard", biz_id=biz_id))
    session["business_id"] = businesses[0].id
    return redirect(url_for("dashboard", biz_id=businesses[0].id))


@app.route("/businesses/new", methods=["GET", "POST"])
def new_business():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            biz = repo.create_business(name)
            _seed_categories(biz.id)
            session["business_id"] = biz.id
            return redirect(url_for("dashboard", biz_id=biz.id))
    return render_template("new_business.html", currency=CURRENCY)


@app.route("/businesses/<int:biz_id>/switch")
def switch_business(biz_id):
    session["business_id"] = biz_id
    return redirect(url_for("dashboard", biz_id=biz_id))


@app.route("/businesses/<int:biz_id>/rename", methods=["POST"])
def rename_business(biz_id):
    name = request.form.get("name", "").strip()
    if name:
        repo.rename_business(biz_id, name)
    return redirect(url_for("dashboard", biz_id=biz_id))


@app.route("/businesses/<int:biz_id>/delete", methods=["POST"])
def delete_business(biz_id):
    repo.delete_business(biz_id)
    session.pop("business_id", None)
    return redirect(url_for("index"))


# ── Dashboard ───────────────────────────────────────────────────────────────

@app.route("/businesses/<int:biz_id>")
def dashboard(biz_id):
    biz = repo.get_business(biz_id)
    if not biz:
        return redirect(url_for("index"))
    session["business_id"] = biz_id
    businesses = repo.list_businesses()
    summary = repo.get_summary(biz_id)
    recent = repo.list_transactions(biz_id, limit=5)
    return render_template("dashboard.html",
                           biz=biz, businesses=businesses,
                           summary=summary, recent=recent,
                           currency=CURRENCY)


# ── Transactions ───────────────────────────────────────────────────────────

@app.route("/businesses/<int:biz_id>/transactions")
def transactions(biz_id):
    biz = repo.get_business(biz_id)
    businesses = repo.list_businesses()
    type_filter = request.args.get("type")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    txns = repo.list_transactions(biz_id,
                                  type_=type_filter or None,
                                  date_from=date_from or None,
                                  date_to=date_to or None,
                                  limit=200)
    return render_template("transactions.html",
                           biz=biz, businesses=businesses, txns=txns,
                           type_filter=type_filter, date_from=date_from,
                           date_to=date_to, currency=CURRENCY)


@app.route("/businesses/<int:biz_id>/transactions/add", methods=["GET", "POST"])
def add_transaction(biz_id):
    biz = repo.get_business(biz_id)
    businesses = repo.list_businesses()
    type_ = request.args.get("type", "income")

    if request.method == "POST":
        type_ = request.form.get("type", "income")
        amount_raw = request.form.get("amount", "").replace(",", "")
        description = request.form.get("description", "").strip() or None
        date = request.form.get("date", "")
        category_id = request.form.get("category_id") or None
        new_cat = request.form.get("new_category", "").strip()

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            categories = repo.list_categories(biz_id, type_)
            return render_template("add_transaction.html", biz=biz,
                                   businesses=businesses, categories=categories,
                                   type_=type_, currency=CURRENCY,
                                   error="Please enter a valid amount greater than zero.")

        if new_cat:
            cat = repo.get_or_create_category(biz_id, new_cat, type_)
            category_id = cat.id
        elif category_id:
            category_id = int(category_id)

        repo.add_transaction(biz_id, type_, amount,
                             description=description,
                             date=date or None,
                             category_id=category_id)
        return redirect(url_for("transactions", biz_id=biz_id))

    categories = repo.list_categories(biz_id, type_)
    return render_template("add_transaction.html", biz=biz,
                           businesses=businesses, categories=categories,
                           type_=type_, currency=CURRENCY, error=None)


@app.route("/businesses/<int:biz_id>/transactions/<int:txn_id>/edit", methods=["GET", "POST"])
def edit_transaction(biz_id, txn_id):
    biz = repo.get_business(biz_id)
    businesses = repo.list_businesses()
    txn = repo.get_transaction(txn_id)
    if not txn:
        return redirect(url_for("transactions", biz_id=biz_id))

    if request.method == "POST":
        type_ = request.form.get("type", "income")
        amount_raw = request.form.get("amount", "").replace(",", "")
        description = request.form.get("description", "").strip() or None
        date = request.form.get("date", "")
        category_id = request.form.get("category_id") or None
        new_cat = request.form.get("new_category", "").strip()

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            categories = repo.list_categories(biz_id, txn.type)
            return render_template("edit_transaction.html", biz=biz,
                                   businesses=businesses, txn=txn,
                                   categories=categories, currency=CURRENCY,
                                   error="Please enter a valid amount greater than zero.")

        if new_cat:
            cat = repo.get_or_create_category(biz_id, new_cat, type_)
            category_id = cat.id
        elif category_id:
            category_id = int(category_id)

        repo.update_transaction(txn_id, type_, amount,
                                description=description,
                                date=date or None,
                                category_id=category_id)
        return redirect(url_for("transactions", biz_id=biz_id))

    categories = repo.list_categories(biz_id, txn.type)
    return render_template("edit_transaction.html", biz=biz,
                           businesses=businesses, txn=txn,
                           categories=categories, currency=CURRENCY, error=None)


@app.route("/businesses/<int:biz_id>/transactions/<int:txn_id>/delete", methods=["POST"])
def delete_transaction(biz_id, txn_id):
    repo.delete_transaction(txn_id)
    return redirect(url_for("transactions", biz_id=biz_id))


# ── Summary ───────────────────────────────────────────────────────────────────

@app.route("/businesses/<int:biz_id>/summary")
def summary(biz_id):
    biz = repo.get_business(biz_id)
    businesses = repo.list_businesses()
    period = request.args.get("period", "all")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    from datetime import date as dt
    today = dt.today()

    if period == "month":
        date_from = today.strftime("%Y-%m-01")
        date_to = str(today)
    elif period == "year":
        date_from = today.strftime("%Y-01-01")
        date_to = str(today)
    elif period == "custom":
        pass
    else:
        date_from = date_to = None

    s = repo.get_summary(biz_id, date_from=date_from, date_to=date_to)
    return render_template("summary.html", biz=biz, businesses=businesses,
                           summary=s, period=period,
                           date_from=date_from, date_to=date_to,
                           currency=CURRENCY)


# ── Categories ────────────────────────────────────────────────────────────────

@app.route("/businesses/<int:biz_id>/categories", methods=["GET", "POST"])
def categories(biz_id):
    biz = repo.get_business(biz_id)
    businesses = repo.list_businesses()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        type_ = request.form.get("type", "income")
        if name:
            repo.get_or_create_category(biz_id, name, type_)
        return redirect(url_for("categories", biz_id=biz_id))
    cats = repo.list_categories(biz_id)
    return render_template("categories.html", biz=biz, businesses=businesses,
                           cats=cats, currency=CURRENCY)


# ── CSV Export ────────────────────────────────────────────────────────────────

@app.route("/businesses/<int:biz_id>/export")
def export(biz_id):
    biz = repo.get_business(biz_id)
    txns = repo.list_transactions(biz_id, limit=100_000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Business", "ID", "Date", "Type", "Category", "Amount", "Description"])
    for t in txns:
        writer.writerow([biz.name, t.id, t.date, t.type,
                         t.category_name or "", f"{t.amount:.2f}", t.description or ""])
    output.seek(0)
    filename = f"{biz.name.replace(' ', '_')}_transactions.csv"
    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name=filename)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_categories(business_id):
    defaults = [
        ("Sales", "income"), ("Services", "income"), ("Other Income", "income"),
        ("Salaries", "expense"), ("Rent", "expense"), ("Utilities", "expense"),
        ("Marketing", "expense"), ("Supplies", "expense"), ("Other Expense", "expense"),
    ]
    for name, type_ in defaults:
        repo.get_or_create_category(business_id, name, type_)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
