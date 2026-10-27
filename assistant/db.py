"""Read-only access to the PBS data for the assistant.

The assistant queries app/data/monthly_drug.parquet (exported from the PostgreSQL
materialised view mv_monthly_drug) through DuckDB, so it runs anywhere without a
database server. Only single SELECT statements are allowed.
"""
from pathlib import Path
import re

import duckdb

DATA = Path(__file__).resolve().parent.parent / "app" / "data" / "monthly_drug.parquet"
MAX_ROWS = 200

_con = None


def connect():
    global _con
    if _con is None:
        _con = duckdb.connect()
        _con.execute(f"CREATE VIEW monthly_drug AS SELECT * FROM read_parquet('{DATA.as_posix()}')")
    return _con


_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|alter|attach|copy|pragma|install|load|export)\b", re.I)


def check_sql(sql: str) -> str | None:
    """Return an error message if the SQL is not a single read-only query, else None."""
    s = sql.strip().rstrip(";")
    if ";" in s:
        return "Only one SQL statement is allowed."
    if not re.match(r"^\s*(select|with)\b", s, re.I):
        return "Only SELECT queries are allowed."
    if _FORBIDDEN.search(s):
        return "The query contains a forbidden keyword. Only read-only SELECT queries are allowed."
    return None


def run_sql(sql: str):
    """Run a read-only query. Returns (columns, rows, error)."""
    err = check_sql(sql)
    if err:
        return [], [], err
    try:
        cur = connect().execute(sql.strip().rstrip(";"))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
        return cols, rows, None
    except Exception as e:  # return the database error so the model can fix its query
        return [], [], f"{type(e).__name__}: {e}"
