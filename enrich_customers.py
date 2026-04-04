"""
enrich_customers.py — Enrich NetSuite reference customers with NAICS codes and business summaries.

Input:  Customers Filtered.csv  (648 rows)
Output: customers filtered enriched.xlsx

Usage:
    cd /Users/brianoneill/Desktop/TAL_CC_clean
    source venv/bin/activate
    python3 enrich_customers.py
"""

import json
import re
import time

import anthropic
import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import get_anthropic_key, MODEL
from db import log_ai_call

INPUT_FILE  = "Customers Filtered.csv"
OUTPUT_FILE = "customers filtered enriched.xlsx"

NEW_COLS = [
    "naics_code",
    "naics_description",
    "industry",
    "sub_industry",
    "what_they_do",
    "business_model",
    "confidence",
    "enrichment_source",
    "enrichment_notes",
]


def scrape_website(url: str, timeout: int = 8) -> tuple[str | None, str]:
    """Fetch URL and return (text[:1500], error_msg). error_msg is '' on success."""
    if not url or not url.startswith("http"):
        return None, "no valid URL"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:1500], ""
    except Exception as e:
        return None, str(e)[:120]


def is_real_highlights(text: str) -> bool:
    """True if Highlights has substantive content (not just a URL)."""
    if not text or len(text) < 100:
        return False
    # Just a URL line — no spaces except maybe after newline
    first_line = text.strip().split("\n")[0].strip()
    if first_line.startswith("http") and " " not in first_line and len(text) < 120:
        return False
    return True


def call_claude(client, name, website, vertical, active_suite, annual_revenue, billing_state, content):
    prompt = f"""You are enriching a database of NetSuite customers for a sales rep.

Company: {name}
Website: {website}
NetSuite Vertical: {vertical}
NetSuite Modules: {active_suite}
Annual Revenue: {annual_revenue}
Billing State: {billing_state}

Website content:
{content}

Extract the following and return as JSON only. No explanation outside the JSON.

{{
  "naics_code": "6-digit NAICS code as a string, e.g. 311941",
  "naics_description": "Full NAICS description, e.g. Mayonnaise, Dressing, and Other Prepared Sauce Manufacturing",
  "industry": "Clean normalized industry label, e.g. Food & Beverage Manufacturing",
  "sub_industry": "More specific, e.g. Condiments and Sauces",
  "what_they_do": "1-2 sentences describing what this company actually does, written plainly",
  "business_model": "One of: manufacturer, distributor, retailer, services, SaaS, nonprofit, other",
  "confidence": "One of: high, medium, low — based on how clear the website content was"
}}

Rules:
- Use the NetSuite Vertical and Modules as strong signals for industry classification
- If the website content is vague or generic, set confidence to low
- naics_code must be exactly 6 digits as a string
- Return only the JSON object, nothing else"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    return prompt, json.loads(raw)


def main():
    df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")

    for col in NEW_COLS:
        df[col] = ""

    client = anthropic.Anthropic(api_key=get_anthropic_key())

    total = len(df)
    enriched_highlights = 0
    enriched_scraped = 0
    failed = 0
    parse_errors = 0

    print(f"Starting enrichment of {total} rows → {OUTPUT_FILE}\n")

    for idx, row in df.iterrows():
        name         = row.get("Name", "")
        website      = row.get("Web Address", "")
        vertical     = row.get("Vertical", "")
        active_suite = row.get("Active Suite", "")
        annual_rev   = row.get("Annual Revenue", "")
        billing_st   = row.get("Billing State/Province", "")
        highlights   = row.get("Highlights", "")

        # Determine content source
        if is_real_highlights(highlights):
            content = highlights[:1500]
            source  = "highlights"
        else:
            content, err = scrape_website(website)
            if content:
                source = "scraped"
            else:
                df.at[idx, "enrichment_source"] = "failed"
                df.at[idx, "enrichment_notes"]  = err or "no content"
                failed += 1
                _progress(idx, total, enriched_highlights, enriched_scraped, failed, parse_errors)
                continue

        # Claude call
        try:
            prompt, result = call_claude(
                client, name, website, vertical, active_suite, annual_rev, billing_st, content
            )
            for col in ["naics_code", "naics_description", "industry", "sub_industry",
                        "what_they_do", "business_model", "confidence"]:
                df.at[idx, col] = str(result.get(col, ""))
            df.at[idx, "enrichment_source"] = source

            try:
                log_ai_call({
                    "rep_id": "brianoneill",
                    "call_type": "customer_enrichment",
                    "prompt_used": prompt,
                    "model_version": MODEL,
                    "queried_at": pd.Timestamp.utcnow().isoformat(),
                })
            except Exception:
                pass

            if source == "highlights":
                enriched_highlights += 1
            else:
                enriched_scraped += 1

        except json.JSONDecodeError as e:
            df.at[idx, "enrichment_source"] = source
            df.at[idx, "enrichment_notes"]  = f"JSON parse error: {str(e)[:80]}"
            parse_errors += 1
        except Exception as e:
            df.at[idx, "enrichment_source"] = source
            df.at[idx, "enrichment_notes"]  = f"Claude error: {str(e)[:80]}"
            parse_errors += 1

        _progress(idx, total, enriched_highlights, enriched_scraped, failed, parse_errors)
        time.sleep(0.5)

    df.to_excel(OUTPUT_FILE, index=False)

    print(f"\n{'='*50}")
    print(f"Done. Saved to {OUTPUT_FILE}")
    print(f"  Total rows:           {total}")
    print(f"  Enriched (highlights):{enriched_highlights}")
    print(f"  Enriched (scraped):   {enriched_scraped}")
    print(f"  Failed (no content):  {failed}")
    print(f"  Claude parse errors:  {parse_errors}")
    print(f"  Success rate:         {(enriched_highlights+enriched_scraped)/total*100:.1f}%")


def _progress(idx, total, h, s, f, p):
    row_num = idx + 1  # type: ignore[operator]
    if row_num % 25 == 0 or row_num == total:
        print(f"[{row_num}/{total}] {h+s} enriched ({h} highlights, {s} scraped) | {f} failed | {p} parse errors")


if __name__ == "__main__":
    main()
