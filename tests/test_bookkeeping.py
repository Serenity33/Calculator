"""Basic tests for the bookkeeping app (uses a temp DB)."""

import os
import tempfile
import pytest
import bookkeeping.db as _db_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Give each test its own isolated SQLite database."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(_db_module, "DB_PATH", db_path)
    _db_module.init_db()
    yield


from bookkeeping.db import init_db
from bookkeeping import repository as repo


def test_create_and_list_businesses():
    b1 = repo.create_business("Acme Ltd")
    b2 = repo.create_business("Beta Co")
    names = {b.name for b in repo.list_businesses()}
    assert "Acme Ltd" in names and "Beta Co" in names


def test_duplicate_business_raises():
    repo.create_business("Acme Ltd")
    with pytest.raises(Exception):
        repo.create_business("Acme Ltd")


def test_rename_business():
    b = repo.create_business("Old Name")
    assert repo.rename_business(b.id, "New Name")
    assert repo.get_business(b.id).name == "New Name"


def test_delete_business():
    b = repo.create_business("Temp Co")
    assert repo.delete_business(b.id)
    assert repo.get_business(b.id) is None


def test_create_category():
    b = repo.create_business("Biz")
    cat = repo.create_category(b.id, "Sales", "income")
    assert cat.name == "Sales" and cat.type == "income"


def test_get_or_create_category_idempotent():
    b = repo.create_business("Biz")
    c1 = repo.get_or_create_category(b.id, "Sales", "income")
    c2 = repo.get_or_create_category(b.id, "Sales", "income")
    assert c1.id == c2.id


def test_list_categories_by_type():
    b = repo.create_business("Biz")
    repo.create_category(b.id, "Sales", "income")
    repo.create_category(b.id, "Rent", "expense")
    assert len(repo.list_categories(b.id, "income")) == 1
    assert len(repo.list_categories(b.id, "expense")) == 1


def test_add_and_list_transactions():
    b = repo.create_business("Biz")
    repo.add_transaction(b.id, "income", 500.0, "First sale", "2025-01-10")
    repo.add_transaction(b.id, "expense", 100.0, "Office supplies", "2025-01-11")
    assert len(repo.list_transactions(b.id)) == 2


def test_transaction_type_filter():
    b = repo.create_business("Biz")
    repo.add_transaction(b.id, "income", 200.0, date="2025-01-01")
    repo.add_transaction(b.id, "expense", 50.0, date="2025-01-02")
    incomes = repo.list_transactions(b.id, type_="income")
    assert len(incomes) == 1 and all(t.type == "income" for t in incomes)


def test_transaction_date_filter():
    b = repo.create_business("Biz")
    repo.add_transaction(b.id, "income", 100.0, date="2025-01-01")
    repo.add_transaction(b.id, "income", 200.0, date="2025-03-15")
    txns = repo.list_transactions(b.id, date_from="2025-02-01", date_to="2025-12-31")
    assert len(txns) == 1 and txns[0].amount == 200.0


def test_delete_transaction():
    b = repo.create_business("Biz")
    t = repo.add_transaction(b.id, "income", 100.0, date="2025-01-01")
    assert repo.delete_transaction(t.id)
    assert len(repo.list_transactions(b.id)) == 0


def test_transactions_cascade_delete_with_business():
    b = repo.create_business("Biz")
    repo.add_transaction(b.id, "income", 100.0, date="2025-01-01")
    repo.delete_business(b.id)
    assert repo.get_business(b.id) is None


def test_summary_net():
    b = repo.create_business("Biz")
    repo.add_transaction(b.id, "income", 1000.0, date="2025-01-01")
    repo.add_transaction(b.id, "expense", 400.0, date="2025-01-02")
    s = repo.get_summary(b.id)
    assert s["total_income"] == 1000.0
    assert s["total_expense"] == 400.0
    assert s["net"] == 600.0


def test_summary_date_range():
    b = repo.create_business("Biz")
    repo.add_transaction(b.id, "income", 500.0, date="2025-01-05")
    repo.add_transaction(b.id, "income", 300.0, date="2025-06-01")
    s = repo.get_summary(b.id, date_from="2025-06-01", date_to="2025-12-31")
    assert s["total_income"] == 300.0


def test_summary_by_category():
    b = repo.create_business("Biz")
    cat = repo.create_category(b.id, "Sales", "income")
    repo.add_transaction(b.id, "income", 200.0, date="2025-01-01", category_id=cat.id)
    repo.add_transaction(b.id, "income", 300.0, date="2025-01-02", category_id=cat.id)
    s = repo.get_summary(b.id)
    sales_row = next(r for r in s["by_category"] if r["name"] == "Sales")
    assert sales_row["total"] == 500.0


def test_csv_export():
    import csv, tempfile, os
    b = repo.create_business("Export Biz")
    repo.add_transaction(b.id, "income", 999.0, "Big sale", "2025-02-01")
    from bookkeeping.export import export_csv
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        path = f.name
    try:
        count = export_csv(b.id, path)
        assert count == 1
        with open(path, newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0][0] == "Business"
        assert rows[1][2] == "2025-02-01"
        assert rows[1][5] == "999.00"
    finally:
        os.unlink(path)
