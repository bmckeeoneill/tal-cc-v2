"""
content_utils.py — Claude-powered content library matching for TAL Command Center.
"""

import json

import db
from config import get_anthropic_key, MODEL, DAILY_AI_CALL_BUDGET


def get_relevant_resources(
    account_name: str,
    industry: str,
    tech_stack,
    signal_summaries: str,
) -> list[dict]:
    """
    Pass account context + full content library to Claude.
    Returns list of matching doc dicts (id, title, url) — max 3.
    Returns empty list if nothing is relevant or Claude errors.
    """
    import anthropic
    import datetime

    library = db.get_content_library()
    if not library:
        return []

    tech = tech_stack
    if isinstance(tech, list):
        tech = ", ".join(tech)

    prompt = (
        f"You are helping a NetSuite sales rep identify relevant content for a prospect account.\n\n"
        f"Account name: {account_name}\n"
        f"Industry: {industry or 'unknown'}\n"
        f"Tech stack: {tech or 'unknown'}\n"
        f"Recent signal summaries: {signal_summaries or 'none'}\n\n"
        f"Here is the available content library:\n"
        f"{json.dumps([{'id': d['id'], 'title': d['title'], 'summary': d['summary']} for d in library], indent=2)}\n\n"
        "Return a JSON array of document IDs that are relevant to this account. Maximum 3. "
        "Return an empty array if nothing is a strong fit. "
        "The industry field may be sparse — weight account name, tech stack, and signal summaries more heavily. "
        "Return only the JSON array, no other text.\n\n"
        'Example: ["aerospace_defense_erp", "aerospace_defense_blueprint"]'
    )

    try:
        if db.get_today_ai_call_count() >= DAILY_AI_CALL_BUDGET:
            return []
        client = anthropic.Anthropic(api_key=get_anthropic_key())
        resp = client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        db.log_ai_call({
            "rep_id": "brianoneill",
            "call_type": "content_library_selection",
            "prompt_used": prompt,
            "model_version": MODEL,
            "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    except Exception as e:
        print(f"[content_utils] Claude call failed: {e}")
        return []

    # Strip markdown fences if present
    import re
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()

    try:
        ids = json.loads(raw)
        if not isinstance(ids, list):
            return []
    except json.JSONDecodeError as e:
        print(f"[content_utils] JSON parse failed: {e} — raw: {raw[:200]}")
        return []

    id_to_doc = {d["id"]: d for d in library}
    results = []
    for doc_id in ids[:3]:
        doc = id_to_doc.get(doc_id)
        if doc:
            results.append({"id": doc["id"], "title": doc["title"], "url": doc["url"]})

    return results
