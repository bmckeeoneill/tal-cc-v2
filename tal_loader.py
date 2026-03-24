"""
Loads the TAL account list from the most recent CSV in the TAL/ directory.
Drop a new CSV into TAL/ and the app picks it up automatically on next reload.
"""

import csv
import glob
import os

TAL_DIR = os.path.join(os.path.dirname(__file__), "TAL")


def load_tal():
    """Return list of account dicts from the most recent TAL CSV."""
    csvs = glob.glob(os.path.join(TAL_DIR, "*.csv"))
    if not csvs:
        return []

    latest = sorted(csvs, reverse=True)[0]

    accounts = []
    with open(latest, encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            domain_raw = row.get("Company URL/Website URL", "").strip()
            # Strip protocol so we can display cleanly and link consistently
            domain = domain_raw.replace("https://", "").replace("http://", "").rstrip("/")

            accounts.append({
                "id": i,
                "company_name": row.get("Account Name", "").strip(),
                "domain": domain,
                "phone": row.get("Company Phone", "").strip(),
                "city": row.get("Company City", "").strip(),
                "state": row.get("Company State", "").strip(),
                "industry": row.get("Industry", "").strip(),
                "nscorp_url": row.get("Export Link", "").strip(),
                "linkedin_url": row.get("Linkedin Company URL", "").strip(),
                "zi_id": row.get("ZoomInfo Company ID", "").strip(),
                "sales_rep": row.get("Sales Rep", "").strip(),
                # Phase 2+ — placeholders until signals are live
                "score": 0,
                "last_signal_date": None,
                "last_signal_type": None,
                "signal_count": 0,
            })

    return accounts


def get_category_counts() -> dict:
    """Stub — returns empty dict until Phase 4 wires real signal counts."""
    return {}
