"""
One-time (and re-runnable) script to load the TAL CSV into Supabase accounts table.
Run from the project directory: python load_tal.py

Safe to re-run — upserts on (zi_id, rep_id), so duplicate runs won't create duplicates.
Accounts with no zi_id are upserted on (company_name, rep_id) instead.
"""

import os
import csv
import glob
import sys

TAL_DIR = os.path.join(os.path.dirname(__file__), "TAL")
REP_ID  = "brianoneill"

# ---------------------------------------------------------------------------
# Load secrets without Streamlit
# ---------------------------------------------------------------------------

def load_secrets():
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    secrets = {}
    with open(secrets_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                secrets[k.strip()] = v.strip().strip('"')
    return secrets

# ---------------------------------------------------------------------------
# Parse CSV
# ---------------------------------------------------------------------------

def load_csv() -> list[dict]:
    csvs = glob.glob(os.path.join(TAL_DIR, "*.csv"))
    if not csvs:
        sys.exit("No CSV files found in TAL/")

    latest = sorted(csvs, reverse=True)[0]
    print(f"Loading: {os.path.basename(latest)}")

    rows = []
    with open(latest, encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            domain_raw = row.get("Company URL/Website URL", "").strip()
            domain = domain_raw.replace("https://", "").replace("http://", "").rstrip("/")

            zi_id = row.get("ZoomInfo Company ID", "").strip()

            rows.append({
                "zi_id":        zi_id or None,
                "company_name": row.get("Account Name", "").strip(),
                "domain":       domain or None,
                "phone":        row.get("Company Phone", "").strip() or None,
                "street":       row.get("Company Street", "").strip() or None,
                "city":         row.get("Company City", "").strip() or None,
                "state":        row.get("Company State", "").strip() or None,
                "zip":          row.get("Company Zip", "").strip() or None,
                "country":      row.get("Company Country", "").strip() or None,
                "industry":     row.get("Industry", "").strip() or None,
                "nscorp_url":   row.get("Export Link", "").strip() or None,
                "linkedin_url": row.get("Linkedin Company URL", "").strip() or None,
                "sales_rep":    row.get("Sales Rep", "").strip() or None,
                "rep_id":       REP_ID,
            })

    print(f"  {len(rows)} accounts parsed from CSV")
    return rows

# ---------------------------------------------------------------------------
# Upsert to Supabase
# ---------------------------------------------------------------------------

def upsert(rows: list[dict], secrets: dict) -> None:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(secrets["DATABASE_URL"])
    cur  = conn.cursor()

    cols = ["zi_id","company_name","domain","phone","street","city","state","zip",
            "country","industry","nscorp_url","linkedin_url","sales_rep","rep_id"]

    with_zi = [r for r in rows if r["zi_id"]]
    without = [r for r in rows if not r["zi_id"]]

    if with_zi:
        psycopg2.extras.execute_values(cur, f"""
            INSERT INTO accounts ({",".join(cols)})
            VALUES %s
            ON CONFLICT (zi_id, rep_id) DO UPDATE SET
                company_name  = EXCLUDED.company_name,
                domain        = EXCLUDED.domain,
                phone         = EXCLUDED.phone,
                street        = EXCLUDED.street,
                city          = EXCLUDED.city,
                state         = EXCLUDED.state,
                zip           = EXCLUDED.zip,
                country       = EXCLUDED.country,
                industry      = EXCLUDED.industry,
                nscorp_url    = EXCLUDED.nscorp_url,
                linkedin_url  = EXCLUDED.linkedin_url,
                sales_rep     = EXCLUDED.sales_rep,
                updated_at    = now()
        """, [[r[c] for c in cols] for r in with_zi])
        print(f"  Upserted {len(with_zi)} accounts (by zi_id)")

    if without:
        psycopg2.extras.execute_values(cur, f"""
            INSERT INTO accounts ({",".join(cols)})
            VALUES %s
            ON CONFLICT (company_name, rep_id) DO UPDATE SET
                domain        = EXCLUDED.domain,
                phone         = EXCLUDED.phone,
                street        = EXCLUDED.street,
                city          = EXCLUDED.city,
                state         = EXCLUDED.state,
                zip           = EXCLUDED.zip,
                country       = EXCLUDED.country,
                industry      = EXCLUDED.industry,
                nscorp_url    = EXCLUDED.nscorp_url,
                linkedin_url  = EXCLUDED.linkedin_url,
                sales_rep     = EXCLUDED.sales_rep,
                updated_at    = now()
        """, [[r[c] for c in cols] for r in without])
        print(f"  Upserted {len(without)} accounts (no zi_id, by company_name)")

    conn.commit()
    cur.close()
    conn.close()

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify(secrets: dict) -> None:
    import psycopg2

    conn = psycopg2.connect(secrets["DATABASE_URL"])
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM accounts WHERE rep_id = %s", (REP_ID,))
    count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT industry) FROM accounts WHERE rep_id = %s AND industry IS NOT NULL", (REP_ID,))
    industries = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT state) FROM accounts WHERE rep_id = %s AND state IS NOT NULL", (REP_ID,))
    states = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(f"\nVerification:")
    print(f"  Accounts in Supabase : {count}")
    print(f"  Unique industries    : {industries}")
    print(f"  Unique states        : {states}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    secrets = load_secrets()
    rows    = load_csv()
    upsert(rows, secrets)
    verify(secrets)
    print("\nDone.")
