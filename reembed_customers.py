"""
reembed_customers.py — Re-embed all customers using rich text.

Old embedding text: company_name | naics_code naics_description | industry
New embedding text: company_name + industry + sub_industry + naics_description
                    + business_type + business_model + what_they_do
                    + highlights + references_descriptors

Run once from the project root:
    source venv/bin/activate
    python3 reembed_customers.py

Cost estimate: ~6,500 records × ~150 tokens avg = ~1M tokens
text-embedding-3-small: $0.02/1M tokens → under $0.02 total
"""

import os
import re
import sys
import time
import psycopg2
import psycopg2.extras
import openai

BATCH_SIZE = 200
MODEL = "text-embedding-3-small"


def get_db_conn():
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    content = open(secrets_path).read()
    m = re.search(r'DATABASE_URL\s*=\s*"([^"]+)"', content)
    if not m:
        raise RuntimeError("DATABASE_URL not found in secrets.toml")
    return psycopg2.connect(m.group(1))


def get_openai_key():
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    content = open(secrets_path).read()
    m = re.search(r'\[openai\].*?api_key\s*=\s*"([^"]+)"', content, re.DOTALL)
    if m:
        return m.group(1)
    raise RuntimeError("OpenAI API key not found in secrets.toml [openai] section")


def build_embed_text(row: dict) -> str:
    """Build rich embedding text from all descriptive fields."""
    parts = []

    # Company identity
    if row.get("company_name"):
        parts.append(row["company_name"])

    # Industry classification
    industry_parts = []
    if row.get("industry"):
        industry_parts.append(row["industry"])
    if row.get("sub_industry"):
        industry_parts.append(row["sub_industry"])
    if industry_parts:
        parts.append("Industry: " + " | ".join(industry_parts))

    if row.get("naics_description"):
        parts.append("NAICS: " + row["naics_description"])

    if row.get("business_type"):
        parts.append("Business type: " + row["business_type"])

    if row.get("business_model"):
        parts.append("Business model: " + row["business_model"])

    if row.get("company_size"):
        parts.append("Size: " + row["company_size"])

    # Rich descriptions — highest signal
    if row.get("what_they_do"):
        parts.append("What they do: " + row["what_they_do"])

    if row.get("highlights"):
        # Strip URLs from highlights — they add noise
        h = re.sub(r'https?://\S+', '', row["highlights"]).strip()
        if h:
            parts.append("Highlights: " + h[:500])

    if row.get("references_descriptors"):
        parts.append("Reference context: " + row["references_descriptors"][:300])

    return "\n".join(parts)


def main():
    print("=== Customer Re-Embedding ===")
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Fetch all customers
    cur.execute("""
        SELECT id, company_name, industry, sub_industry, naics_code,
               naics_description, business_type, business_model, company_size,
               what_they_do, highlights, references_descriptors
        FROM customers
        ORDER BY id
    """)
    rows = cur.fetchall()
    total = len(rows)
    print(f"Fetched {total} customers\n")

    oa = openai.OpenAI(api_key=get_openai_key())

    updated = 0
    errors = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = rows[batch_start : batch_start + BATCH_SIZE]
        texts = [build_embed_text(dict(r)) for r in batch]
        ids   = [r["id"] for r in batch]

        # Show a sample from first batch
        if batch_start == 0:
            print("Sample embedding text (first record):")
            print("-" * 60)
            print(texts[0][:400])
            print("-" * 60)
            print()

        try:
            resp = oa.embeddings.create(model=MODEL, input=texts)
            embeddings = [e.embedding for e in resp.data]
        except Exception as e:
            print(f"  [ERROR] OpenAI batch {batch_start}-{batch_start+len(batch)}: {e}")
            errors += len(batch)
            time.sleep(2)
            continue

        # Update each row
        update_cur = conn.cursor()
        for cid, emb in zip(ids, embeddings):
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            update_cur.execute(
                "UPDATE customers SET embedding = %s::vector WHERE id = %s",
                (emb_str, str(cid))
            )
        conn.commit()
        update_cur.close()

        updated += len(batch)
        pct = updated / total * 100
        end_idx = min(batch_start + BATCH_SIZE, total)
        print(f"  [{pct:5.1f}%] Updated {updated}/{total} (batch {batch_start+1}–{end_idx})")

        # Small pause to stay under rate limits
        time.sleep(0.3)

    cur.close()
    conn.close()

    print(f"\nDone. Updated: {updated} | Errors: {errors}")


if __name__ == "__main__":
    main()
