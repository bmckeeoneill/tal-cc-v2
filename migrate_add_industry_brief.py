"""
One-time migration: add industry_brief column to accounts table.

Run once:
    source venv/bin/activate
    python3 migrate_add_industry_brief.py
"""
import os
import re
import psycopg2

def get_db_conn():
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    content = open(secrets_path).read()
    m = re.search(r'DATABASE_URL\s*=\s*"([^"]+)"', content)
    if not m:
        raise RuntimeError("DATABASE_URL not found in secrets.toml")
    return psycopg2.connect(m.group(1))

def main():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE accounts
        ADD COLUMN IF NOT EXISTS industry_brief TEXT;
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Done — industry_brief column added (or already existed).")

if __name__ == "__main__":
    main()
