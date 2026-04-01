"""
Pipeline orchestrator for TAL Command Center.

Run order:
  1. Process all unprocessed signals_raw rows (extract, match, summarize, outreach)
  2. Run weekly analysis for every account that got new signals this week
  3. Run weekly digest scoring across all active accounts
  4. Print summary

Usage:
    cd /Users/brianoneill/Desktop/TAL_CC_clean
    source venv/bin/activate
    python3 run_pipeline.py
"""

import os
import re
from datetime import date, datetime, timedelta, timezone

import anthropic

import db
import signal_processor
from config import get_anthropic_key, MODEL, REP_ID

SIGNAL_TYPE_WEIGHTS = {
    "exec_hire": 3,
    "funding": 3,
    "expansion": 2,
    "tech_adoption": 2,
    "event": 1,
    "other": 1,
}


def _week_of() -> str:
    """Return ISO date string for Monday of the current week."""
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def run_weekly_analysis(client: anthropic.Anthropic, account_id: str, company_name: str) -> None:
    """Generate and store weekly analysis for one account."""
    signals = db.get_signals_for_account(account_id, days=7)
    if not signals:
        return

    signal_block = "\n".join(
        f"- [{s['signal_type']}] {s['headline']}: {s['summary']}" for s in signals
    )

    prompt = (
        "You are a NetSuite sales intelligence assistant. "
        "Analyze the following signals for a single account and provide a running summary.\n\n"
        f"Account: {company_name}\n"
        f"Signals this week:\n{signal_block}\n\n"
        "Answer these three questions in 3-5 sentences total:\n"
        "1. What is happening at this account?\n"
        "2. What is the overall signal trend?\n"
        "3. Is this account heating up, cooling down, or flat?\n\n"
        "End your response with exactly one word on a new line: HEATING, COOLING, or FLAT."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()

    # Extract trend from last line
    lines = text.strip().splitlines()
    last_line = lines[-1].strip().upper()
    trend = last_line if last_line in ("HEATING", "COOLING", "FLAT") else "FLAT"
    summary = "\n".join(lines[:-1]).strip() if trend != "FLAT" or len(lines) > 1 else text

    now = datetime.now(timezone.utc)

    db.log_ai_call({
        "rep_id": REP_ID,
        "call_type": "weekly_analysis",
        "prompt_used": prompt,
        "model_version": MODEL,
        "queried_at": now.isoformat(),
    })

    try:
        db.insert_weekly_analysis({
            "account_id": account_id,
            "rep_id": REP_ID,
            "week_of": _week_of(),
            "summary": summary,
            "trend": trend.lower(),
            "model_version": MODEL,
            "generated_at": now.isoformat(),
        })
    except Exception as e:
        # UNIQUE constraint fires if analysis already ran this week for this account — skip
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            pass
        else:
            raise


def run_weekly_digest(client: anthropic.Anthropic, updated_account_ids: set[str]) -> None:
    """Score accounts that had signals this week and write top 5 to weekly_digest."""
    if not updated_account_ids:
        return

    account_names = {a["id"]: a["company_name"] for a in db.get_account_names(REP_ID)}
    scored = []

    for account_id in updated_account_ids:
        signals = db.get_signals_for_account(account_id, days=7)
        if not signals:
            continue

        # Weighted score
        score = 0
        for s in signals:
            score += SIGNAL_TYPE_WEIGHTS.get(s.get("signal_type", "other"), 1)

        # Trend bonus
        top_signal_type = signals[0].get("signal_type", "other") if signals else "other"

        scored.append({
            "account_id": account_id,
            "company_name": account_names.get(account_id, "Unknown"),
            "score": score,
            "signal_count": len(signals),
            "top_signal_type": top_signal_type,
            "signals": signals,
        })

    # Sort by score desc, take top 5
    scored.sort(key=lambda x: x["score"], reverse=True)
    top5 = scored[:5]

    if not top5:
        return

    # Generate reasoning for each via Claude
    week = _week_of()
    now = datetime.now(timezone.utc)
    rows = []

    for rank, item in enumerate(top5, start=1):
        signal_block = "\n".join(
            f"- [{s['signal_type']}] {s['headline']}" for s in item["signals"][:5]
        )
        prompt = (
            f"In 1-2 sentences, explain why {item['company_name']} is a priority account "
            f"to contact this week based on these signals:\n{signal_block}"
        )
        reasoning = client.messages.create(
            model=MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text.strip()

        db.log_ai_call({
            "rep_id": REP_ID,
            "call_type": "digest_reasoning",
            "prompt_used": prompt,
            "model_version": MODEL,
            "queried_at": now.isoformat(),
        })

        rows.append({
            "rep_id": REP_ID,
            "week_of": week,
            "account_id": item["account_id"],
            "rank": rank,
            "score": item["score"],
            "top_signal_type": item["top_signal_type"],
            "reason": reasoning,
            "signal_count": item["signal_count"],
            "created_at": now.isoformat(),
        })

    db.insert_weekly_digest(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== TAL Command Center — Pipeline Run ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    client = anthropic.Anthropic(api_key=get_anthropic_key())

    # Step 1: Process raw signals
    print("Step 1: Processing raw signals...")
    counts = signal_processor.process_all_signals()
    print(f"  Total: {counts['total']} | Matched: {counts['matched']} | "
          f"Review queue: {counts['review_queue']} | Errors: {counts['errors']}\n")

    if counts["total"] == 0:
        print("  No unprocessed signals.\n")

    # Summary
    pending = db.get_pending_review_count(REP_ID)
    print("=== Summary ===")
    print(f"  Signals processed : {counts['matched']}")
    print(f"  Routed to review  : {counts['review_queue']}")
    print(f"  Pending review    : {pending}")
    print(f"  Errors            : {counts['errors']}")
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # NOTE: Weekly analysis and digest scoring are deferred to a future phase.


if __name__ == "__main__":
    main()
