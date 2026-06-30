"""
Multi-Business Bookkeeping CLI
Usage: python3 -m bookkeeping
"""

from datetime import date, datetime
from typing import Optional

from . import repository as repo
from .db import init_db
from .export import export_csv


WIDTH = 60
SEP = "─" * WIDTH


def header(text: str) -> None:
    print(f"\n{'═' * WIDTH}")
    print(f"  {text}")
    print(f"{'═' * WIDTH}")


def section(text: str) -> None:
    print(f"\n{SEP}")
    print(f"  {text}")
    print(SEP)


def money(amount: float) -> str:
    return f"£{amount:,.2f}"


def print_table(rows: list[list], col_widths: list[int], headers: list[str]) -> None:
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        cells = [str(c)[:w] for c, w in zip(row, col_widths)]
        print(fmt.format(*cells))


def prompt(text: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {text}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)
    return val or (default or "")


def prompt_float(text: str) -> Optional[float]:
    raw = prompt(text)
    try:
        val = float(raw.replace(",", "").replace("£", "").replace("$", ""))
        if val <= 0:
            print("  Amount must be greater than zero.")
            return None
        return val
    except ValueError:
        print("  Invalid amount.")
        return None


def prompt_date(text: str) -> Optional[str]:
    raw = prompt(text, default=str(date.today()))
    try:
        datetime.strptime(raw, "%Y-%m-%d")
        return raw
    except ValueError:
        print("  Invalid date. Use YYYY-MM-DD format.")
        return None


def choose(options: list[str], label: str = "choice") -> Optional[int]:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    raw = prompt(f"Enter {label} number (or 0 to cancel)")
    try:
        n = int(raw)
        if n == 0:
            return None
        if 1 <= n <= len(options):
            return n - 1
        print("  Invalid selection.")
        return None
    except ValueError:
        print("  Invalid selection.")
        return None


def select_or_create_business() -> Optional[int]:
    businesses = repo.list_businesses()
    header("BOOKKEEPING — Select Business")
    if businesses:
        print("\n  Existing businesses:\n")
        options = [b.name for b in businesses] + ["[ + Add new business ]"]
        idx = choose(options, "business")
        if idx is None:
            return None
        if idx < len(businesses):
            return businesses[idx].id
    name = prompt("Business name")
    if not name:
        print("  Name cannot be empty.")
        return None
    biz = repo.create_business(name)
    print(f"\n  Created business: {biz.name}")
    _seed_default_categories(biz.id)
    return biz.id


def _seed_default_categories(business_id: int) -> None:
    defaults = [
        ("Sales", "income"), ("Services", "income"), ("Other Income", "income"),
        ("Salaries", "expense"), ("Rent", "expense"), ("Utilities", "expense"),
        ("Marketing", "expense"), ("Supplies", "expense"), ("Other Expense", "expense"),
    ]
    for name, type_ in defaults:
        repo.get_or_create_category(business_id, name, type_)


def main_menu(business_id: int) -> None:
    biz = repo.get_business(business_id)
    if not biz:
        print("  Business not found.")
        return
    while True:
        header(f"BOOKKEEPING — {biz.name.upper()}")
        print("""
  1. Add income
  2. Add expense
  3. View transactions
  4. Financial summary
  5. Manage categories
  6. Export to CSV
  7. Manage businesses
  0. Quit
""")
        choice = prompt("Select option")
        if choice == "1":
            add_transaction(business_id, "income")
        elif choice == "2":
            add_transaction(business_id, "expense")
        elif choice == "3":
            view_transactions(business_id)
        elif choice == "4":
            financial_summary(business_id)
        elif choice == "5":
            manage_categories(business_id)
        elif choice == "6":
            do_export(business_id)
        elif choice == "7":
            new_id = manage_businesses(business_id)
            if new_id != business_id:
                if new_id is None:
                    return
                business_id = new_id
                biz = repo.get_business(business_id)
        elif choice == "0":
            print("\n  Goodbye!\n")
            raise SystemExit(0)
        else:
            print("  Invalid option.")


def add_transaction(business_id: int, type_: str) -> None:
    label = type_.capitalize()
    section(f"Add {label}")
    amount = None
    while amount is None:
        amount = prompt_float(f"{label} amount (£)")
    categories = repo.list_categories(business_id, type_)
    cat_names = [c.name for c in categories] + ["[ + New category ]", "[ No category ]"]
    print("\n  Category:\n")
    idx = choose(cat_names, "category")
    if idx is None:
        return
    category_id: Optional[int] = None
    if idx < len(categories):
        category_id = categories[idx].id
    elif idx == len(categories):
        name = prompt("New category name")
        if name:
            cat = repo.get_or_create_category(business_id, name, type_)
            category_id = cat.id
    description = prompt("Description (optional)")
    txn_date = None
    while txn_date is None:
        txn_date = prompt_date("Date")
    txn = repo.add_transaction(
        business_id=business_id, type_=type_, amount=amount,
        description=description or None, date=txn_date, category_id=category_id,
    )
    print(f"\n  ✓ Recorded: {money(txn.amount)} on {txn.date}")


def view_transactions(business_id: int) -> None:
    section("View Transactions")
    print("""
  Filter by:
  1. All transactions
  2. Income only
  3. Expenses only
  4. Date range
  0. Back
""")
    choice = prompt("Select filter")
    type_filter: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    if choice == "0":
        return
    elif choice == "2":
        type_filter = "income"
    elif choice == "3":
        type_filter = "expense"
    elif choice == "4":
        date_from = prompt_date("From date")
        date_to = prompt_date("To date")
        if not date_from or not date_to:
            return
    raw = prompt("How many transactions to show", default="50")
    try:
        limit = max(1, int(raw))
    except ValueError:
        limit = 50
    txns = repo.list_transactions(
        business_id, type_=type_filter, date_from=date_from, date_to=date_to, limit=limit
    )
    section(f"Transactions ({len(txns)} shown)")
    if not txns:
        print("  No transactions found.")
        return
    rows = []
    for t in txns:
        sign = "+" if t.type == "income" else "-"
        rows.append([t.date, t.type.capitalize(), t.category_name or "—",
                     f"{sign}{money(t.amount)}", (t.description or "")[:28], str(t.id)])
    print_table(rows, [10, 9, 16, 12, 28, 5], ["Date", "Type", "Category", "Amount", "Description", "ID"])
    print("\n  Enter transaction ID to delete, or press Enter to go back.")
    raw = prompt("Transaction ID (or Enter)").strip()
    if raw.isdigit():
        if repo.delete_transaction(int(raw)):
            print(f"  ✓ Transaction {raw} deleted.")
        else:
            print(f"  Transaction {raw} not found.")


def financial_summary(business_id: int) -> None:
    section("Financial Summary")
    print("""
  Period:
  1. All time
  2. This month
  3. This year
  4. Custom date range
""")
    choice = prompt("Select period", default="1")
    today = date.today()
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    if choice == "2":
        date_from = today.strftime("%Y-%m-01")
        date_to = str(today)
    elif choice == "3":
        date_from = today.strftime("%Y-01-01")
        date_to = str(today)
    elif choice == "4":
        date_from = prompt_date("From date")
        date_to = prompt_date("To date")
        if not date_from or not date_to:
            return
    summary = repo.get_summary(business_id, date_from=date_from, date_to=date_to)
    biz = repo.get_business(business_id)
    period_label = f"{date_from} → {date_to}" if date_from else "All time"
    print(f"""
  Business : {biz.name}
  Period   : {period_label}
  {SEP}
  Total Income   : {money(summary['total_income']):>12}
  Total Expenses : {money(summary['total_expense']):>12}
  {SEP}
  Net Profit/Loss: {money(summary['net']):>12}  {'▲ PROFIT' if summary['net'] >= 0 else '▼ LOSS'}
  Transactions   : {summary['transaction_count']:>12}
""")
    if summary["by_category"]:
        print("  Breakdown by category:\n")
        rows = []
        for c in summary["by_category"]:
            rows.append([c["name"] or "Uncategorised", c["type"].capitalize(),
                         money(c["total"]), str(c["count"])])
        print_table(rows, [22, 10, 12, 8], ["Category", "Type", "Total", "Count"])
    input("\n  Press Enter to continue...")


def manage_categories(business_id: int) -> None:
    while True:
        section("Manage Categories")
        cats = repo.list_categories(business_id)
        if cats:
            rows = [[c.name, c.type.capitalize(), str(c.id)] for c in cats]
            print_table(rows, [28, 10, 6], ["Name", "Type", "ID"])
        else:
            print("  No categories yet.")
        print("""
  1. Add income category
  2. Add expense category
  0. Back
""")
        choice = prompt("Select option")
        if choice == "0":
            return
        elif choice in ("1", "2"):
            type_ = "income" if choice == "1" else "expense"
            name = prompt(f"Category name ({type_})")
            if name:
                repo.get_or_create_category(business_id, name, type_)
                print(f"  ✓ Category '{name}' added.")
        else:
            print("  Invalid option.")


def do_export(business_id: int) -> None:
    section("Export to CSV")
    biz = repo.get_business(business_id)
    default_path = f"{biz.name.replace(' ', '_')}_transactions.csv"
    path = prompt("Save to file", default=default_path)
    if not path:
        return
    count = export_csv(business_id, path)
    print(f"\n  ✓ Exported {count} transactions to {path}")


def manage_businesses(current_business_id: int) -> Optional[int]:
    while True:
        section("Manage Businesses")
        businesses = repo.list_businesses()
        if businesses:
            rows = [[b.name, b.created, str(b.id)] for b in businesses]
            print_table(rows, [28, 12, 6], ["Name", "Created", "ID"])
        else:
            print("  No businesses yet.")
        print("""
  1. Switch to a different business
  2. Add new business
  3. Rename current business
  4. Delete a business
  0. Back
""")
        choice = prompt("Select option")
        if choice == "0":
            return current_business_id
        elif choice == "1":
            if not businesses:
                print("  No businesses to switch to.")
                continue
            idx = choose([b.name for b in businesses], "business")
            if idx is not None:
                return businesses[idx].id
        elif choice == "2":
            name = prompt("New business name")
            if name:
                biz = repo.create_business(name)
                _seed_default_categories(biz.id)
                print(f"  ✓ Created: {biz.name}")
                if prompt("Switch to this business? (y/n)", default="y").lower() == "y":
                    return biz.id
        elif choice == "3":
            biz = repo.get_business(current_business_id)
            new_name = prompt("New name", default=biz.name)
            if new_name and new_name != biz.name:
                repo.rename_business(current_business_id, new_name)
                print(f"  ✓ Renamed to: {new_name}")
        elif choice == "4":
            if not businesses:
                continue
            idx = choose([b.name for b in businesses], "business to delete")
            if idx is not None:
                biz = businesses[idx]
                confirm = prompt(f"Delete '{biz.name}' and ALL its data? Type YES to confirm")
                if confirm == "YES":
                    deleted_current = biz.id == current_business_id
                    repo.delete_business(biz.id)
                    print(f"  ✓ Deleted: {biz.name}")
                    if deleted_current:
                        remaining = repo.list_businesses()
                        return remaining[0].id if remaining else None
                else:
                    print("  Cancelled.")
        else:
            print("  Invalid option.")


def run() -> None:
    init_db()
    business_id = select_or_create_business()
    if business_id is None:
        return
    main_menu(business_id)
