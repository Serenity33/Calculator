# Multi-Business Bookkeeping

A terminal-based bookkeeping application for managing finances across multiple businesses.

## Features

- **Multiple businesses** — create, rename, switch between, and delete businesses
- **Income & expense tracking** — record transactions with date, amount, description, and category
- **Custom categories** — per-business income and expense categories (seeded with sensible defaults)
- **Financial summary** — profit/loss report filterable by period (all time, month, year, custom)
- **Category breakdown** — see totals grouped by category
- **Transaction history** — view and delete transactions with optional filters
- **CSV export** — export any business's transactions to a CSV file

## Requirements

- Python 3.10+
- No third-party runtime dependencies (SQLite is built-in)

## Run

```bash
python3 main.py
# or
python3 -m bookkeeping
```

## Tests

```bash
pip install pytest
pytest tests/
```

## Data storage

Transactions are stored in `~/.bookkeeping/data.db` (SQLite).

## Project structure

```
bookkeeping/
  __init__.py
  __main__.py   — entry point for `python3 -m bookkeeping`
  db.py         — SQLite connection + schema init
  models.py     — dataclasses
  repository.py — all database queries
  cli.py        — interactive menu-driven CLI
  export.py     — CSV export
main.py         — convenience entry point
tests/
  test_bookkeeping.py
```
