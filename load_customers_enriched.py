"""
load_customers_enriched.py — Replace customers table with enriched dataset.

Truncates existing customers table and loads from 'customers filtered enriched.xlsx'.
648 rows, 627 with NAICS codes. Skips embedding rebuild — matching is now NAICS-based.

Usage:
    cd /Users/brianoneill/Desktop/TAL_CC_clean
    source venv/bin/activate
    python3 load_customers_enriched.py
"""

import sys
from pathlib import Path
import pandas as pd

from db import get_client

INPUT_FILE = "customers filtered enriched.xlsx"
BATCH_SIZE = 50


def main():
    if not Path(INPUT_FILE).exists():
        print(f"ERROR: {INPUT_FILE} not found in project root.")
        sys.exit(1)

    df = pd.read_excel(INPUT_FILE, dtype=str).fillna("")
    print(f"Loaded {len(df)} rows from {INPUT_FILE}")

    client = get_client()

    # Truncate existing customers via direct DB connection (avoids API timeout)
    print("Truncating customers table...")
    import re as _re
    from pathlib import Path as _Path
    import psycopg2 as _psycopg2
    _content = _Path(".streamlit/secrets.toml").read_text()
    _m = _re.search(r'DATABASE_URL\s*=\s*"([^"]+)"', _content)
    _conn = _psycopg2.connect(_m.group(1))
    _conn.cursor().execute("TRUNCATE TABLE customers RESTART IDENTITY CASCADE;")
    _conn.commit(); _conn.close()
    print("Truncated.")

    # Build records
    records = []
    skipped = 0
    for _, row in df.iterrows():
        name = (row.get("Name") or "").strip()
        if not name:
            skipped += 1
            continue

        # Clean naics_code — strip float suffix if present (e.g. "423610.0" → "423610")
        raw_naics = str(row.get("naics_code") or "").strip()
        if raw_naics.endswith(".0"):
            raw_naics = raw_naics[:-2]
        if raw_naics == "nan":
            raw_naics = ""

        records.append({
            "company_name":      name,
            "website":           (row.get("Web Address") or "").strip(),
            "industry":          (row.get("industry") or "").strip(),       # enriched clean label
            "sub_industry":      (row.get("sub_industry") or "").strip(),
            "naics_code":        raw_naics,
            "naics_description": (row.get("naics_description") or "").strip(),
            "what_they_do":      (row.get("what_they_do") or "").strip(),
            "business_model":    (row.get("business_model") or "").strip(),
            "revenue_range":     (row.get("Annual Revenue") or "").strip(),
            "state":             (row.get("Billing State/Province") or "").strip(),
            "reference_status":  (row.get("Reference Status") or "").strip(),
            "notes":             (row.get("Highlights") or "").strip(),
        })

    print(f"{len(records)} rows to insert ({skipped} skipped — blank name)")

    inserted = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        client.table("customers").insert(batch).execute()
        inserted += len(batch)
        print(f"  {inserted}/{len(records)} inserted...")

    # Quick summary
    with_naics = sum(1 for r in records if r["naics_code"])
    print(f"\nDone.")
    print(f"  Total inserted:    {inserted}")
    print(f"  With NAICS code:   {with_naics}")
    print(f"  Without NAICS:     {inserted - with_naics}")
    print(f"  Reference Ready:   {sum(1 for r in records if 'Ready' in r['reference_status'])}")
    print(f"  Reference Active:  {sum(1 for r in records if 'Active' in r['reference_status'])}")


if __name__ == "__main__":
    main()
