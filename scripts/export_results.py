"""Run the five analysis SQL files against PostgreSQL and save every result set.

Outputs:
  results/<sql file name>_<n>.csv   one CSV per SELECT in each analysis file
  app/data/monthly_drug.parquet     the pre-aggregated table behind the dashboard

Usage (from the project folder):  python scripts/export_results.py
"""
import re
from pathlib import Path

import pandas as pd

ANALYSES = [
    "05_a1_category_spend",
    "06_a2_burden_share",
    "07_a3_concentration",
    "08_a4_seasonality",
    "09_a5_price_volume",
]

APP_QUERY = """
SELECT m.month_start, m.cal_year, m.cal_month, m.fin_year,
       v.drug_name, v.atc1_code, a.atc1_name, v.scheme_group,
       CAST(v.scripts AS bigint)                 AS scripts,
       CAST(v.total_cost AS double precision)    AS total_cost,
       CAST(v.govt_cost AS double precision)     AS govt_cost,
       CAST(v.patient_cost AS double precision)  AS patient_cost
FROM mv_monthly_drug v
JOIN dim_month m USING (month_key)
JOIN dim_atc1  a USING (atc1_code)
"""


def statements(sql_text):
    """Split a .sql file into statements, dropping comments and psql meta-commands."""
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("\\")]
    text = re.sub(r"--.*", "", "\n".join(lines))
    return [s.strip() for s in text.split(";") if s.strip()]


def export_all(read_sql, root=Path(".")):
    """read_sql: a function that takes a SQL string and returns a DataFrame."""
    (root / "results").mkdir(exist_ok=True)
    (root / "app" / "data").mkdir(parents=True, exist_ok=True)
    for name in ANALYSES:
        selects = [s for s in statements((root / "sql" / f"{name}.sql").read_text())
                   if s.upper().startswith(("SELECT", "WITH"))]
        for n, sql in enumerate(selects, start=1):
            df = read_sql(sql)
            out = root / "results" / f"{name}_{n}.csv"
            df.to_csv(out, index=False)
            print(f"{out}: {len(df)} rows")
    app = read_sql(APP_QUERY)
    out = root / "app" / "data" / "monthly_drug.parquet"
    app.to_parquet(out, index=False)
    print(f"{out}: {len(app)} rows")


if __name__ == "__main__":
    from sqlalchemy import create_engine, text

    engine = create_engine("postgresql+psycopg2://localhost/pbs")

    def read_sql(sql):
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    export_all(read_sql)
