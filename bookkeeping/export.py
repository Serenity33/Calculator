import csv
from . import repository as repo


def export_csv(business_id: int, path: str) -> int:
    txns = repo.list_transactions(business_id, limit=100_000)
    biz = repo.get_business(business_id)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Business", "ID", "Date", "Type", "Category", "Amount", "Description"])
        for t in txns:
            writer.writerow([biz.name, t.id, t.date, t.type,
                             t.category_name or "", f"{t.amount:.2f}", t.description or ""])
    return len(txns)
