"""Convert the PBS Date of Supply workbook (one sheet per financial year) to one CSV.

Usage: python scripts/xlsx_to_csv.py data/raw/dos-jul-2022-to-jul-2026.xlsx data/pbs_dos.csv
Requires: pip install python-calamine  (a fast XLSX reader; openpyxl takes minutes on this file)
"""
import csv
import sys
from python_calamine import CalamineWorkbook

# source column name -> name used in the database
RENAME = {
    "MONTH_OF_SUPPLY": "month_of_supply",
    "ITEM_CODE": "item_code",
    "ATC5_CODE": "atc5_code",
    "DRUG_NAME": "drug_name",
    "PTNT_CTGRY_DRVD_CD": "patient_cat",
    "DRG_TYP_CTGRY": "drg_typ_ctgry",
    "SCRIPT_TYPE": "script_type",
    "PRSCRPTN_CNT": "prescriptions",
    "PATIENT_CONTRIB": "patient_contrib",
    "GOVT_CONTRIB": "govt_contrib",
    "RETAIL_MARKUP": "retail_markup",
    "TOTAL_COST": "total_cost",
    "PATIENT_NET_CONTRIB": "patient_net_contrib",
}
INTS = {"month_of_supply", "prescriptions"}
MONEY = {"patient_contrib", "govt_contrib", "retail_markup", "total_cost", "patient_net_contrib"}

src, dst = sys.argv[1], sys.argv[2]
wb = CalamineWorkbook.from_path(src)
out_cols = list(RENAME.values())

total = 0
with open(dst, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(out_cols)
    for sheet in wb.sheet_names:
        rows = wb.get_sheet_by_name(sheet).to_python()
        header = rows[0] if rows else None
        if header is None or set(header) != set(RENAME):
            print(f"SKIP sheet {sheet}: unexpected header {header}")
            continue
        names = [RENAME[h] for h in header]
        order = [names.index(c) for c in out_cols]
        n = 0
        for row in rows[1:]:
            if row[0] in (None, ""):
                continue
            out = []
            for col, j in zip(out_cols, order):
                v = row[j]
                if col in INTS:
                    v = int(v)
                elif col in MONEY:
                    # the source carries floating-point noise (e.g. 43774.5899999999)
                    v = "" if v in (None, "") else f"{round(float(v), 2):.2f}"
                out.append(v)
            writer.writerow(out)
            n += 1
        total += n
        print(f"{sheet}: {n} rows", flush=True)

print(f"TOTAL: {total} rows -> {dst}")
