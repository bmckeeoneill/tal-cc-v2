"""
load_naics.py — Load NAICS codes and notes from TAL_FINAL_NAICS.csv into accounts table.

Usage:
    cd /Users/brianoneill/Desktop/TAL_CC_clean
    source venv/bin/activate
    python3 load_naics.py
"""

import csv
from rapidfuzz import process, fuzz
from db import get_client


def _clean_naics_code(raw: str) -> str:
    """Strip float suffix (e.g. '423610.0' -> '423610'). Store as text."""
    raw = raw.strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    return raw


def load_naics():
    client = get_client()

    resp = client.table("accounts").select("id, company_name").eq("active", True).execute()
    accounts = resp.data or []
    account_map = {a["company_name"]: a["id"] for a in accounts}
    names = list(account_map.keys())

    updated = 0
    skipped_no_naics = 0
    skipped_no_match = 0

    with open("TAL_FINAL_NAICS.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_code = row.get("naics_code", "").strip()
            if not raw_code:
                skipped_no_naics += 1
                continue

            naics_code = _clean_naics_code(raw_code)
            csv_name = row.get("Account Name", "").strip()

            match = process.extractOne(
                csv_name, names,
                scorer=fuzz.token_set_ratio,
                score_cutoff=85,
            )

            if not match:
                print(f"  NO MATCH: {csv_name}")
                skipped_no_match += 1
                continue

            matched_name, score, _ = match
            account_id = account_map[matched_name]

            client.table("accounts").update({
                "naics_code":        naics_code,
                "naics_description": row.get("naics_description", "").strip() or None,
                "naics_confidence":  row.get("confidence", "").strip() or None,
                "naics_notes":       row.get("notes", "").strip() or None,
            }).eq("id", account_id).execute()

            updated += 1

    print(f"\nDone. Updated: {updated} | Skipped (no NAICS): {skipped_no_naics} | No match: {skipped_no_match}")


if __name__ == "__main__":
    load_naics()
