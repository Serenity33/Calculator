from typing import Optional
from .db import get_connection
from .models import Business, Category, Transaction


def create_business(name: str) -> Business:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO businesses (name) VALUES (?)", (name,))
        row = conn.execute("SELECT * FROM businesses WHERE id = ?", (cur.lastrowid,)).fetchone()
    return Business(**dict(row))


def list_businesses() -> list[Business]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM businesses ORDER BY name").fetchall()
    return [Business(**dict(r)) for r in rows]


def get_business(business_id: int) -> Optional[Business]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    return Business(**dict(row)) if row else None


def delete_business(business_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM businesses WHERE id = ?", (business_id,))
    return cur.rowcount > 0


def rename_business(business_id: int, new_name: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE businesses SET name = ? WHERE id = ?", (new_name, business_id)
        )
    return cur.rowcount > 0


def create_category(business_id: int, name: str, type_: str) -> Category:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO categories (business_id, name, type) VALUES (?, ?, ?)",
            (business_id, name, type_),
        )
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return Category(**dict(row))


def list_categories(business_id: int, type_: Optional[str] = None) -> list[Category]:
    with get_connection() as conn:
        if type_:
            rows = conn.execute(
                "SELECT * FROM categories WHERE business_id = ? AND type = ? ORDER BY name",
                (business_id, type_),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM categories WHERE business_id = ? ORDER BY type, name",
                (business_id,),
            ).fetchall()
    return [Category(**dict(r)) for r in rows]


def get_or_create_category(business_id: int, name: str, type_: str) -> Category:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM categories WHERE business_id = ? AND name = ? AND type = ?",
            (business_id, name, type_),
        ).fetchone()
        if row:
            return Category(**dict(row))
    return create_category(business_id, name, type_)


def add_transaction(
    business_id: int,
    type_: str,
    amount: float,
    description: Optional[str] = None,
    date: Optional[str] = None,
    category_id: Optional[int] = None,
) -> Transaction:
    with get_connection() as conn:
        if date:
            cur = conn.execute(
                "INSERT INTO transactions (business_id, category_id, type, amount, description, date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (business_id, category_id, type_, amount, description, date),
            )
        else:
            cur = conn.execute(
                "INSERT INTO transactions (business_id, category_id, type, amount, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (business_id, category_id, type_, amount, description),
            )
        return _fetch_transaction(conn, cur.lastrowid)


def _fetch_transaction(conn, txn_id: int) -> Transaction:
    row = conn.execute(
        """
        SELECT t.*, c.name AS category_name
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.id = ?
        """,
        (txn_id,),
    ).fetchone()
    return _row_to_transaction(row)


def _row_to_transaction(row) -> Transaction:
    d = dict(row)
    return Transaction(
        id=d["id"],
        business_id=d["business_id"],
        category_id=d["category_id"],
        type=d["type"],
        amount=d["amount"],
        description=d["description"],
        date=d["date"],
        created_at=d["created_at"],
        category_name=d.get("category_name"),
    )


def list_transactions(
    business_id: int,
    type_: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> list[Transaction]:
    clauses = ["t.business_id = ?"]
    params: list = [business_id]

    if type_:
        clauses.append("t.type = ?")
        params.append(type_)
    if date_from:
        clauses.append("t.date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("t.date <= ?")
        params.append(date_to)

    where = " AND ".join(clauses)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT t.*, c.name AS category_name
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE {where}
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_row_to_transaction(r) for r in rows]


def delete_transaction(txn_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    return cur.rowcount > 0


def get_summary(
    business_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    clauses = ["t.business_id = ?"]
    params: list = [business_id]
    if date_from:
        clauses.append("t.date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("t.date <= ?")
        params.append(date_to)
    where = " AND ".join(clauses)

    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN t.type='income'  THEN t.amount ELSE 0 END), 0) AS total_income,
                COALESCE(SUM(CASE WHEN t.type='expense' THEN t.amount ELSE 0 END), 0) AS total_expense,
                COUNT(*) AS transaction_count
            FROM transactions t
            WHERE {where}
            """,
            params,
        ).fetchone()

        cat_rows = conn.execute(
            f"""
            SELECT c.name, t.type,
                   SUM(t.amount) AS total,
                   COUNT(*) AS count
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE {where}
            GROUP BY t.category_id, t.type
            ORDER BY total DESC
            """,
            params,
        ).fetchall()

    return {
        "total_income": row["total_income"],
        "total_expense": row["total_expense"],
        "net": row["total_income"] - row["total_expense"],
        "transaction_count": row["transaction_count"],
        "by_category": [dict(r) for r in cat_rows],
    }
