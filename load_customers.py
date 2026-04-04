"""
load_customers.py — Ingest ~6k NetSuite customer records into Supabase with embeddings.

Usage:
    cd /Users/brianoneill/Desktop/TAL_CC_clean
    source venv/bin/activate
    python3 load_customers.py

CSV expected at: /Users/brianoneill/Desktop/customers.csv

On every run: truncates the customers table before reloading. Full replace, no dedup.
"""

import csv
import re
import sys
import time
from pathlib import Path

from db import embed_text, get_client

CSV_PATH = Path("/Users/brianoneill/Desktop/TAL_CC_clean/customers.csv")
BATCH_SIZE = 100


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    url = re.sub(r"https?://", "", url.strip())
    url = re.sub(r"^www\.", "", url)
    return url.split("/")[0].strip()


def _build_embed_text(row: dict) -> str:
    parts = []
    if row.get("company_name"):
        parts.append(row["company_name"])
    if row.get("naics_description"):
        parts.append(row["naics_description"])
    if row.get("industry"):
        parts.append(row["industry"])
    if row.get("notes"):
        parts.append(row["notes"])
    domain = _extract_domain(row.get("website", ""))
    if domain:
        parts.append(domain)
    return ". ".join(parts)


def _should_skip(row: dict) -> bool:
    name = (row.get("company_name") or "").strip()
    if not name or "blank" in name.lower() or "qa" in name.lower():
        return True
    if not row.get("industry") and not row.get("notes") and not row.get("website"):
        return True
    return False


def main():
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}")
        sys.exit(1)

    client = get_client()

    print("Truncating customers table...")
    client.table("customers").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    rows_to_insert = []
    skipped = 0

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    print(f"Read {len(all_rows)} rows from CSV")

    # Normalize column names (strip whitespace)
    normalized = []
    for raw in all_rows:
        row = {k.strip(): (v.strip() if v else "") for k, v in raw.items()}
        normalized.append(row)

    # Map actual column names to internal field names
    field_map = {
        "company_name":     "Name",
        "website":          "Web Address",
        "industry":         "Vertical",
        "revenue_range":    "Annual Revenue",
        "state":            "Billing State/Province",
        "reference_status": "Reference Status",
        "notes":            "Highlights",
    }

    def get_field(row, field):
        key = field_map.get(field)
        return row.get(key, "") if key else ""

    cleaned = []
    for row in normalized:
        record = {
            "company_name": get_field(row, "company_name"),
            "website":      get_field(row, "website"),
            "industry":     get_field(row, "industry"),
            "revenue_range": get_field(row, "revenue_range"),
            "state":        get_field(row, "state"),
            "reference_status": get_field(row, "reference_status"),
            "notes":        get_field(row, "notes"),
        }
        if _should_skip(record):
            skipped += 1
            continue
        cleaned.append(record)

    print(f"{len(cleaned)} rows to embed and insert, {skipped} skipped")

    inserted = 0
    for batch_start in range(0, len(cleaned), BATCH_SIZE):
        batch = cleaned[batch_start: batch_start + BATCH_SIZE]

        # Build embedding texts
        texts = [_build_embed_text(r) for r in batch]

        # Embed in one API call (OpenAI supports batch input)
        import openai, os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
            if secrets_path.exists():
                content = secrets_path.read_text()
                m = re.search(r'\[openai\].*?api_key\s*=\s*"([^"]+)"', content, re.DOTALL)
                if m:
                    api_key = m.group(1)
        if not api_key:
            print("ERROR: OpenAI API key not found. Add to .streamlit/secrets.toml under [openai] api_key = ...")
            sys.exit(1)

        oa = openai.OpenAI(api_key=api_key)
        resp = oa.embeddings.create(model="text-embedding-3-small", input=texts)
        embeddings = [item.embedding for item in resp.data]

        records = []
        for record, embedding in zip(batch, embeddings):
            records.append({**record, "embedding": embedding})

        client.table("customers").insert(records).execute()
        inserted += len(records)

        if inserted % 500 == 0 or inserted == len(cleaned):
            print(f"  {inserted} / {len(cleaned)} inserted...")

        # Brief pause between batches to stay within rate limits
        time.sleep(0.2)

    print(f"\nDone. {inserted} rows loaded, {skipped} skipped.")


if __name__ == "__main__":
    main()
