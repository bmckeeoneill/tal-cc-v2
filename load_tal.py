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

    latest = sorted(csvs, key=os.path.getmtime, reverse=True)[0]
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

    # Deduplicate by zi_id (keep first occurrence), then by name
    seen_zi, seen_name, deduped = set(), set(), []
    for r in rows:
        key = r["zi_id"] or r["company_name"]
        if key in seen_zi or r["company_name"] in seen_name:
            print(f"  [SKIP duplicate] {r['company_name']}")
            continue
        seen_zi.add(key)
        seen_name.add(r["company_name"])
        deduped.append(r)

    print(f"  {len(rows)} accounts parsed from CSV ({len(deduped)} after dedup)")
    return deduped

# ---------------------------------------------------------------------------
# Upsert to Supabase
# ---------------------------------------------------------------------------

def upsert(rows: list[dict], secrets: dict) -> dict:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(secrets["DATABASE_URL"])
    cur  = conn.cursor()

    cols = ["zi_id","company_name","domain","phone","street","city","state","zip",
            "country","industry","nscorp_url","linkedin_url","sales_rep","rep_id"]

    with_zi = [r for r in rows if r["zi_id"]]
    without = [r for r in rows if not r["zi_id"]]

    # ── Get existing account names before upsert ──────────────────────────────
    cur.execute("SELECT company_name FROM accounts WHERE rep_id = %s AND active = true", (REP_ID,))
    existing_names = {r[0] for r in cur.fetchall()}
    csv_names = {r["company_name"] for r in rows}
    new_names = csv_names - existing_names

    # ── Enrich manually-added accounts (no zi_id) that now appear in CSV with a zi_id ──
    # Without this, the with_zi upsert would create a duplicate instead of enriching.
    enrich_cols = ["zi_id","domain","phone","street","city","state","zip","country","industry","nscorp_url","linkedin_url","sales_rep"]
    for r in with_zi:
        cur.execute(f"""
            UPDATE accounts SET {", ".join(f"{c} = %s" for c in enrich_cols)}, updated_at = now()
            WHERE rep_id = %s AND company_name = %s AND (zi_id IS NULL OR zi_id = '')
              AND active = true
        """, [r[c] for c in enrich_cols] + [REP_ID, r["company_name"]])
    if with_zi:
        conn.commit()

    # ── Upsert accounts in CSV — mark all active, only set assigned=false for new ──
    if with_zi:
        psycopg2.extras.execute_values(cur, f"""
            INSERT INTO accounts ({",".join(cols)}, active, assigned)
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
                active        = true,
                updated_at    = now()
        """, [[r[c] for c in cols] + [True, r["company_name"] not in new_names] for r in with_zi])
        print(f"  Upserted {len(with_zi)} accounts (by zi_id)")

    if without:
        psycopg2.extras.execute_values(cur, f"""
            INSERT INTO accounts ({",".join(cols)}, active, assigned)
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
                active        = true,
                updated_at    = now()
        """, [[r[c] for c in cols] + [True, r["company_name"] not in new_names] for r in without])
        print(f"  Upserted {len(without)} accounts (no zi_id, by company_name)")

    # ── Mark accounts NOT in CSV as inactive ──────────────────────────────────
    removed_names = existing_names - csv_names
    if removed_names:
        cur.execute(
            "UPDATE accounts SET active = false, updated_at = now() WHERE rep_id = %s AND company_name = ANY(%s)",
            (REP_ID, list(removed_names))
        )

    conn.commit()
    cur.close()
    conn.close()

    return {"new": sorted(new_names), "removed": sorted(removed_names)}

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
    changes = upsert(rows, secrets)
    verify(secrets)

    print(f"\n  New accounts added    : {len(changes['new'])}")
    print(f"  Accounts marked inactive: {len(changes['removed'])}")
    if changes["new"]:
        for name in changes["new"]:
            print(f"    + {name}")
    if changes["removed"]:
        print("  Removed:")
        for name in changes["removed"]:
            print(f"    - {name}")
    print("\nDone.")
