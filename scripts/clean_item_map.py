"""Re-encode the PBS item map to UTF-8 and keep one row per item code.

The source file is Windows-1252 encoded, which PostgreSQL (UTF-8) refuses to load.
Usage: python scripts/clean_item_map.py data/raw/pbs-item-drug-map.csv data/item_map.csv
"""
import sys
import pandas as pd

src, dst = sys.argv[1], sys.argv[2]
df = pd.read_csv(src, dtype=str, encoding="cp1252", keep_default_na=False)
df.columns = ["item_code", "drug_name", "form_strength", "atc5_code"]
n_before = len(df)
df = df.drop_duplicates(subset="item_code", keep="last")
df.to_csv(dst, index=False, encoding="utf-8")
print(f"{n_before} rows read, {len(df)} unique item codes written -> {dst}")
