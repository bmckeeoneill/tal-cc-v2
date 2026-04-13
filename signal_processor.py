"""
Signal processing pipeline for TAL Command Center.

Three extraction paths based on signal source:
  Path A — CRM notification (structured parse, no Claude)
  Path B — Screenshot forward (Claude Vision)
  Path C — Text forward (Claude text)

Then for all matched signals: fuzzy account match, summary, outreach suggestion.
Called by run_pipeline.py — do not run directly.
"""

import base64
import json
import os
import re
from datetime import datetime, timezone

import anthropic
from rapidfuzz import fuzz, process as fuzz_process

import db
from config import get_anthropic_key, REP_ID, MODEL, MATCH_THRESHOLD

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SIGNAL_TYPES = ["exec_hire", "funding", "tech_adoption", "expansion", "event", "intent_signal", "crm_other", "other"]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

CRM_SENDER = "unknown-email@nlcorp.com"
BRIAN_SENDERS = {"brian.br.oneill@oracle.com", "bmckeeoneill@gmail.com"}


def _claude_text(client: anthropic.Anthropic, prompt: str, signal_id: str, call_type: str) -> str:
    """Call Claude text, log, return response."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    db.log_ai_call({
        "rep_id": REP_ID,
        "signal_id": signal_id,
        "call_type": call_type,
        "prompt_used": prompt,
        "model_version": MODEL,
        "queried_at": datetime.now(timezone.utc).isoformat(),
    })
    return text


def _claude_vision(client: anthropic.Anthropic, image_b64: str, mime_type: str, signal_id: str) -> dict:
    """
    Call Claude Vision on a base64 image.
    Returns dict with: company_name, what_happened, why_relevant, signal_type
    """
    prompt = (
        "You are analyzing a screenshot forwarded by a sales rep. Extract the following:\n"
        "1. Company name (if visible)\n"
        "2. What is happening (1-2 sentences)\n"
        "3. Why this is relevant to a NetSuite ERP sales rep (1 sentence)\n"
        "4. Signal type: one of exec_hire, funding, tech_adoption, expansion, event, other\n\n"
        "Return only a JSON object with keys: company_name, what_happened, why_relevant, signal_type"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    raw = response.content[0].text.strip()
    db.log_ai_call({
        "rep_id": REP_ID,
        "signal_id": signal_id,
        "call_type": "vision_extraction",
        "prompt_used": prompt,
        "model_version": MODEL,
        "queried_at": datetime.now(timezone.utc).isoformat(),
    })
    # Parse JSON — strip markdown fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"company_name": None, "what_happened": raw, "why_relevant": "", "signal_type": "other"}


# ---------------------------------------------------------------------------
# Source detection
# ---------------------------------------------------------------------------

def detect_source(signal: dict) -> str:
    """
    Returns: 'crm_notification' | 'screenshot_forward' | 'text_forward' | 'events_digest'
    """
    sender = (signal.get("from_email") or "").lower()
    sender_addr = sender.split("<")[-1].strip(">").strip()
    subject = (signal.get("subject") or "").strip().lower()

    if CRM_SENDER in sender_addr:
        return "crm_notification"

    # CRM notification forwarded by Brian: body contains the structured CRM field
    if sender_addr in BRIAN_SENDERS:
        body = (signal.get("body_text") or "")
        if "Associated companies, contacts:" in body:
            return "crm_notification"

    # Events: any email with "event" in subject
    if "event" in subject:
        return "events_digest"

    # Lead capture: forwarded by Brian with subject exactly "lead"
    if subject == "lead":
        return "lead"

    # Watch lead: subject "watch" or "watch lead"
    if subject in ("watch", "watch lead"):
        return "watch"

    # SDR update: forwarded by Brian with subject exactly "sdr"
    if subject == "sdr":
        return "sdr"

    # Contacts capture: forwarded by Brian with subject exactly "contacts"
    if subject == "contacts":
        return "contacts"

    # New account: subject contains "account" (e.g. "account", "new TAL account", "new account")
    if "account" in subject:
        return "account_add"

    # Check if any attachment is an image
    attachments = signal.get("attachments") or []
    if isinstance(attachments, str):
        try:
            attachments = json.loads(attachments)
        except Exception:
            attachments = []

    has_image = any(
        os.path.splitext((a.get("filename") or "").lower())[1] in IMAGE_EXTENSIONS
        for a in attachments
    )

    if has_image:
        return "screenshot_forward"

    return "text_forward"


# ---------------------------------------------------------------------------
# Path A: CRM notification (structured parse)
# ---------------------------------------------------------------------------

def extract_crm_signal(signal: dict) -> tuple[str | None, str | None, str, str]:
    """
    Returns (company_name, contact_name, signal_type, signal_body)
    """
    body = signal.get("body_text") or ""
    subject = signal.get("subject") or ""

    # Company + contact from "Associated companies, contacts:" block
    # Handles both inline format and multi-line bullet format:
    #   Inline:  "Associated companies, contacts: Acme Corp, John Smith"
    #   Bullet:  "Associated companies, contacts:\n\n  *   12345 Acme Corp, John Smith"
    company_name = None
    contact_name = None
    assoc_match = re.search(
        r"Associated companies,\s*contacts:\s*(.+?)(?:NOTICE:|$)",
        body, re.IGNORECASE | re.DOTALL
    )
    if assoc_match:
        block = assoc_match.group(1).strip()
        # Bullet format: * [optional_ns_id] Company, Contact
        bullet_match = re.search(r"\*\s+(?:\d+\s+)?(.+)", block)
        if bullet_match:
            line = bullet_match.group(1).strip()
        else:
            line = block.splitlines()[0].strip()
        parts = line.split(",", 1)
        company_name = parts[0].strip() or None
        contact_name = parts[1].strip() if len(parts) > 1 else None

    # Signal type from subject keywords
    subj_lower = subject.lower()
    if any(k in subj_lower for k in ["registered for", "virtual event", "did not attend", "webinar"]):
        signal_type = "event"
    elif any(k in subj_lower for k in ["intent signal", "zoominfo"]):
        signal_type = "intent_signal"
    else:
        signal_type = "crm_other"

    # Signal body from "Task:" field
    task_match = re.search(r"Task:\s*(.+?)(?:\n\n|\Z)", body, re.IGNORECASE | re.DOTALL)
    signal_body = task_match.group(1).strip() if task_match else body[:500]

    return company_name, contact_name, signal_type, signal_body


# ---------------------------------------------------------------------------
# Path B: Screenshot (vision)
# ---------------------------------------------------------------------------

def _get_first_image(signal: dict) -> tuple[str, str] | None:
    """Return (base64_data, mime_type) for first image attachment, or None."""
    attachments = signal.get("attachments") or []
    if isinstance(attachments, str):
        try:
            attachments = json.loads(attachments)
        except Exception:
            return None

    for att in attachments:
        filename = att.get("filename") or ""
        ext = os.path.splitext(filename.lower())[1]
        if ext in IMAGE_EXTENSIONS:
            raw = att.get("data_base64") or ""
            # Fix URL-safe base64
            padded = raw.replace("-", "+").replace("_", "/")
            padded += "=" * (-len(padded) % 4)
            mime = att.get("mime_type") or "image/png"
            return padded, mime
    return None


# ---------------------------------------------------------------------------
# Fuzzy account matching
# ---------------------------------------------------------------------------

_STRIP_SUFFIXES = re.compile(
    r"\b(inc|llc|ltd|corp|co|company|group|holdings|international|the)\b\.?",
    re.IGNORECASE,
)
_STRIP_PUNCT = re.compile(r"[^\w\s]")


def _normalize(name: str) -> str:
    name = _STRIP_PUNCT.sub(" ", name)
    name = _STRIP_SUFFIXES.sub(" ", name)
    return " ".join(name.split()).lower()


def match_account(company_name: str, account_names: list[dict]) -> tuple[str | None, str | None, float]:
    """Returns (account_id | None, best_match_name | None, confidence 0-100)."""
    if not company_name or not account_names:
        return None, None, 0.0

    query = _normalize(company_name)
    normalized_names = [_normalize(a["company_name"]) for a in account_names]
    result = fuzz_process.extractOne(query, normalized_names, scorer=fuzz.token_set_ratio)

    if result is None:
        return None, None, 0.0

    _, score, idx = result
    best_name = account_names[idx]["company_name"]
    capped = min(float(score), 99.99)
    if score >= MATCH_THRESHOLD:
        return account_names[idx]["id"], best_name, capped
    return None, best_name, capped


# ---------------------------------------------------------------------------
# Review queue routing
# ---------------------------------------------------------------------------

def route_to_review_queue(signal: dict, company_name: str | None, best_match: str | None, confidence: float, reason: str) -> None:
    db.insert_review_queue({
        "raw_id": signal["id"],
        "rep_id": REP_ID,
        "extracted_name": company_name,
        "best_match_name": best_match,
        "match_confidence": round(confidence, 2),
        "reason": reason,
        "reviewed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Write matched signal + outreach
# ---------------------------------------------------------------------------

def write_matched_signal(
    client: anthropic.Anthropic,
    signal: dict,
    account_id: str,
    company_name: str,
    signal_type: str,
    confidence: float,
    summary: str,
    source: str,
    headline: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)

    # Use provided headline; fall back to subject (never use bare screenshot filenames)
    resolved_headline = headline or signal.get("subject") or ""

    db.insert_signals_processed({
        "raw_id": signal["id"],
        "account_id": account_id,
        "rep_id": REP_ID,
        "signal_type": signal_type,
        "signal_source": source,
        "source": source,
        "headline": resolved_headline,
        "summary": summary,
        "signal_date": now.date().isoformat(),
        "match_confidence": round(confidence, 2),
        "model_version": MODEL,
        "processed_at": now.isoformat(),
        "file_url": signal.get("file_url"),
    })

    # Update accounts table
    sb = db.get_client()
    existing = sb.table("accounts").select("signal_count").eq("id", account_id).single().execute()
    current_count = (existing.data or {}).get("signal_count") or 0
    sb.table("accounts").update({
        "signal_count": current_count + 1,
        "last_signal_date": now.date().isoformat(),
        "last_signal_type": signal_type,
        "updated_at": now.isoformat(),
    }).eq("id", account_id).execute()

    # Outreach suggestion
    outreach_prompt = (
        "You are Brian O'Neill, a NetSuite ERP sales rep. "
        "Write a short prospecting email to a decision-maker at the company below.\n\n"
        f"Signal type: {signal_type}\n"
        f"Prospect company: {company_name}\n"
        f"Industry: {signal.get('industry', 'unknown')}\n"
        f"Signal summary: {summary}\n\n"
        "Structure (follow exactly, 3 parts):\n"
        "1. Industry-specific hook: one sentence. Something specific and a little absurd that shows you "
        "understand their world. Written like something a rep heard in the field, not a case study.\n"
        "2. Signal or trigger reference: one sentence. Why you are reaching out right now.\n"
        "3. CTA: direct and cheeky. Example: 'Is this something you are thinking about?'\n\n"
        "Tone rules (hard rules, no exceptions):\n"
        "- No em dashes\n"
        "- No hyphens used as dashes between phrases\n"
        "- No hyphenated words\n"
        "- No complex or formal vocabulary\n"
        "- Short sentences only\n"
        "- Sounds like a human wrote it quickly, not an AI or consultant\n"
        "- No filler words\n"
        "- No bold font\n\n"
        "Length: Two sentences plus a CTA. That is it.\n"
        "Address it to the prospect (use 'Hi [Name]' as placeholder). Sign off as Brian."
    )
    email_body = _claude_text(client, outreach_prompt, signal["id"], "outreach_suggestion")

    db.insert_outreach_suggestion({
        "rep_id": REP_ID,
        "account_id": account_id,
        "signal_id": signal["id"],
        "trigger_type": signal_type,
        "email_body": email_body,
        "model_version": MODEL,
        "generated_at": now.isoformat(),
    })


# ---------------------------------------------------------------------------
# SDR table parser
# ---------------------------------------------------------------------------

def _parse_sdr_table(body: str) -> list[dict]:
    """
    Parse SDR email table. Looks for rows with Name and BDR columns.
    Returns list of {name, sdr_name} dicts.
    """
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    results = []
    name_idx = bdr_idx = None

    for line in lines:
        # Try to detect delimiter
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
        elif "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
        else:
            continue

        if len(parts) < 2:
            continue

        # Find header row
        if name_idx is None:
            lower_parts = [p.lower() for p in parts]
            if "name" in lower_parts:
                try:
                    name_idx = lower_parts.index("name")
                    # BDR column: prefer "bdr" exact, fall back to contains "bdr"
                    bdr_candidates = [i for i, p in enumerate(lower_parts) if "bdr" in p and "status" not in p and "date" not in p and "lead" not in p]
                    bdr_idx = bdr_candidates[0] if bdr_candidates else None
                except Exception:
                    pass
            continue

        # Data row
        if name_idx is not None and bdr_idx is not None:
            try:
                name = parts[name_idx] if name_idx < len(parts) else None
                sdr_raw = parts[bdr_idx] if bdr_idx < len(parts) else None
                if name and sdr_raw and name.lower() not in ("name", ""):
                    # Normalize SDR name: "Lastname, Firstname" → "Firstname Lastname"
                    if "," in sdr_raw:
                        last, first = sdr_raw.split(",", 1)
                        sdr_name = f"{first.strip()} {last.strip()}"
                    else:
                        sdr_name = sdr_raw.strip()
                    results.append({"name": name, "sdr_name": sdr_name})
            except Exception:
                continue

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_all_signals() -> dict:
    client = anthropic.Anthropic(api_key=get_anthropic_key())
    account_names = db.get_account_names(REP_ID)
    signals = db.get_unprocessed_signals(REP_ID)

    counts = {"total": len(signals), "matched": 0, "review_queue": 0, "errors": 0}

    for signal in signals:
        try:
            source = detect_source(signal)
            company_name = None
            signal_type = "other"
            summary = ""
            screenshot_headline = None

            # ── Account add ───────────────────────────────────────────────
            if source == "account_add":
                image = _get_first_image(signal)
                acct_info = {}

                account_prompt = (
                    "You are analyzing content forwarded by a sales rep to add a new prospect account.\n"
                    "Extract the following fields:\n"
                    "  company_name (required)\n"
                    "  domain (website, e.g. 'acme.com')\n"
                    "  industry\n"
                    "  street\n"
                    "  city\n"
                    "  state (2-letter abbreviation)\n"
                    "  zip\n"
                    "  phone\n"
                    "  linkedin_url\n\n"
                    "Return only a JSON object with these keys. Use null for any field you cannot find."
                )

                if image:
                    image_b64, mime_type = image
                    response = client.messages.create(
                        model=MODEL, max_tokens=512,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                            {"type": "text", "text": account_prompt},
                        ]}],
                    )
                else:
                    body_excerpt = (signal.get("body_text") or "")[:2000]
                    response = client.messages.create(
                        model=MODEL, max_tokens=512,
                        messages=[{"role": "user", "content": f"{account_prompt}\n\nCONTENT:\n{body_excerpt}"}],
                    )

                db.log_ai_call({"rep_id": REP_ID, "signal_id": signal["id"], "call_type": "account_add_extraction",
                                "prompt_used": account_prompt, "model_version": MODEL,
                                "queried_at": datetime.now(timezone.utc).isoformat()})
                raw = response.content[0].text.strip()
                raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
                try:
                    acct_info = json.loads(raw)
                except Exception:
                    acct_info = {}

                company_name_extracted = (acct_info.get("company_name") or "").strip()
                if not company_name_extracted:
                    print(f"  ✗ [account_add] Could not extract company name from signal {signal['id']}")
                    db.mark_signal_processed(signal["id"])
                    counts["errors"] += 1
                    continue

                new_acct = {
                    "company_name": company_name_extracted,
                    "domain":       acct_info.get("domain"),
                    "industry":     acct_info.get("industry"),
                    "street":       acct_info.get("street"),
                    "city":         acct_info.get("city"),
                    "state":        acct_info.get("state"),
                    "zip":          acct_info.get("zip"),
                    "phone":        acct_info.get("phone"),
                    "linkedin_url": acct_info.get("linkedin_url"),
                    "rep_id":       REP_ID,
                    "active":       True,
                    "assigned":     True,
                }
                acct_id = db.create_account(new_acct)
                db.mark_signal_processed(signal["id"])
                counts["matched"] += 1
                print(f"  ✓ [account_add] Created account: {company_name_extracted!r} (id={acct_id})")
                continue

            # ── Events digest ─────────────────────────────────────────────
            if source == "events_digest":
                import events_parser
                n = events_parser.process_events_email(signal)
                db.mark_signal_processed(signal["id"])
                counts["matched"] += n
                print(f"  ✓ [events_digest] {n} events parsed and stored")
                continue

            # ── Lead capture ──────────────────────────────────────────────
            if source == "lead":
                image = _get_first_image(signal)
                company_name = None
                website = None
                if image:
                    image_b64, mime_type = image
                    lead_prompt = (
                        "You are analyzing an image forwarded by a sales rep as a potential lead.\n"
                        "Extract:\n"
                        "1. Company name (if visible)\n"
                        "2. Website URL (if visible)\n\n"
                        "Return only a JSON object with keys: company_name, website\n"
                        "If you cannot find a value, use null."
                    )
                    response = client.messages.create(
                        model=MODEL, max_tokens=256,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                            {"type": "text", "text": lead_prompt},
                        ]}],
                    )
                    raw = response.content[0].text.strip()
                    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
                    db.log_ai_call({"rep_id": REP_ID, "signal_id": signal["id"], "call_type": "lead_vision",
                                    "prompt_used": lead_prompt, "model_version": MODEL,
                                    "queried_at": datetime.now(timezone.utc).isoformat()})
                    try:
                        result = json.loads(raw)
                        company_name = result.get("company_name")
                        website = result.get("website")
                    except Exception:
                        pass

                db.insert_lead({
                    "company_name": company_name,
                    "website": website,
                    "file_url": signal.get("file_url"),
                    "raw_email_id": signal["id"],
                    "status": "active",
                })
                db.mark_signal_processed(signal["id"])
                counts["matched"] += 1
                print(f"  ✓ [lead] {company_name or 'unknown'} captured")
                continue

            # ── Watch lead ────────────────────────────────────────────────
            if source == "watch":
                body = signal.get("body_text") or ""

                # Extract NS URL from body
                ns_url = None
                for token in body.split():
                    if "nlcorp.app.netsuite.com" in token or "custjob.nl" in token:
                        ns_url = token.strip("()<>\"'")
                        break

                # Extract notes: body text minus any URLs
                import re as _re
                notes_raw = _re.sub(r'https?://\S+', '', body).strip()
                notes = notes_raw if notes_raw else None

                # Try vision extraction for company name + LSAD date from screenshot
                company_name = None
                lsad_date = None
                website = None
                image = _get_first_image(signal)
                if image:
                    image_b64, mime_type = image
                    watch_prompt = (
                        "You are analyzing a screenshot of a NetSuite lead record.\n"
                        "Extract the following fields exactly as they appear:\n"
                        "1. company_name: the Company Name field value\n"
                        "2. lsad_date: the LSAD Date field value (format M/D/YYYY or MM/DD/YYYY)\n"
                        "3. website: the Web Address field value\n\n"
                        "Return only a JSON object with keys: company_name, lsad_date, website\n"
                        "Use null for any field you cannot find."
                    )
                    vision_resp = client.messages.create(
                        model=MODEL, max_tokens=256,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                            {"type": "text", "text": watch_prompt},
                        ]}],
                    )
                    raw = vision_resp.content[0].text.strip()
                    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
                    db.log_ai_call({"rep_id": REP_ID, "signal_id": signal["id"], "call_type": "watch_vision",
                                    "prompt_used": watch_prompt, "model_version": MODEL,
                                    "queried_at": datetime.now(timezone.utc).isoformat()})
                    try:
                        extracted = json.loads(raw)
                        company_name = extracted.get("company_name")
                        website = extracted.get("website")
                        lsad_raw = extracted.get("lsad_date")
                        if lsad_raw:
                            from datetime import datetime as _dt
                            for fmt in ("%m/%d/%Y", "%-m/%-d/%Y", "%m/%d/%y"):
                                try:
                                    lsad_date = _dt.strptime(lsad_raw, fmt).strftime("%Y-%m-%d")
                                    break
                                except ValueError:
                                    continue
                    except Exception:
                        pass

                db.insert_watch_lead({
                    "company_name": company_name,
                    "ns_url": ns_url,
                    "lsad_date": lsad_date,
                    "website": website,
                    "notes": notes,
                    "raw_email_id": signal["id"],
                    "status": "active",
                })
                db.mark_signal_processed(signal["id"])
                counts["matched"] += 1
                print(f"  ✓ [watch] {company_name or 'unknown'} added to watch list")
                continue

            # ── SDR update ────────────────────────────────────────────────
            if source == "sdr":
                body = signal.get("body_text") or ""
                # Parse table rows: look for lines with pipe or tab-separated columns
                # Find header row to locate Name and BDR columns
                sdr_entries = _parse_sdr_table(body)
                matched_count = 0
                for entry in sdr_entries:
                    acct_name = entry.get("name")
                    sdr_name = entry.get("sdr_name")
                    if not acct_name or not sdr_name:
                        continue
                    account_id, best_match, confidence = match_account(acct_name, account_names)
                    if account_id:
                        db.update_sdr(account_id, sdr_name)
                        matched_count += 1
                        print(f"  ✓ [sdr] {acct_name!r} → SDR: {sdr_name}")
                    else:
                        route_to_review_queue(signal, acct_name, best_match, confidence,
                                              f"SDR update: low confidence match ({confidence:.0f}%)")
                        counts["review_queue"] += 1
                db.mark_signal_processed(signal["id"])
                counts["matched"] += matched_count
                print(f"  ✓ [sdr] {matched_count} SDR assignments updated")
                continue

            # ── Contacts capture ──────────────────────────────────────────
            if source == "contacts":
                image = _get_first_image(signal)
                contacts_extracted = []
                if image:
                    image_b64, mime_type = image
                    contacts_prompt = (
                        "You are analyzing a screenshot or business card scan forwarded by a sales rep.\n"
                        "Extract all visible contacts. For each person found, extract:\n"
                        "- name (full name)\n"
                        "- title (job title or role)\n"
                        "- email\n"
                        "- phone\n"
                        "- linkedin_url\n"
                        "- company_name\n\n"
                        "Return a JSON array of contact objects. Use null for any field you cannot find.\n"
                        'Example: [{"name": "Jane Doe", "title": "CFO", "email": "jane@acme.com", '
                        '"phone": null, "linkedin_url": null, "company_name": "Acme Corp"}]'
                    )
                    response = client.messages.create(
                        model=MODEL, max_tokens=512,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                            {"type": "text", "text": contacts_prompt},
                        ]}],
                    )
                    raw = response.content[0].text.strip()
                    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
                    db.log_ai_call({"rep_id": REP_ID, "signal_id": signal["id"], "call_type": "contacts_vision",
                                    "prompt_used": contacts_prompt, "model_version": MODEL,
                                    "queried_at": datetime.now(timezone.utc).isoformat()})
                    try:
                        contacts_extracted = json.loads(raw)
                        if not isinstance(contacts_extracted, list):
                            contacts_extracted = []
                    except Exception:
                        contacts_extracted = []
                else:
                    # No image — try body text extraction
                    body = (signal.get("body_text") or "")[:2000]
                    contacts_text_prompt = (
                        "Extract all visible contacts from this email body. For each person found, extract:\n"
                        "- name, title, email, phone, linkedin_url, company_name\n\n"
                        "Return a JSON array of contact objects. Use null for missing fields.\n\n"
                        f"EMAIL BODY:\n{body}"
                    )
                    raw_text = _claude_text(client, contacts_text_prompt, signal["id"], "contacts_text_extraction")
                    raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text).rstrip("```").strip()
                    try:
                        contacts_extracted = json.loads(raw_text)
                        if not isinstance(contacts_extracted, list):
                            contacts_extracted = []
                    except Exception:
                        contacts_extracted = []

                inserted = 0
                for contact in contacts_extracted:
                    company_name = contact.get("company_name")
                    if company_name:
                        account_id_match, best_match, confidence = match_account(company_name, account_names)
                    else:
                        account_id_match, best_match, confidence = None, None, 0.0

                    if account_id_match and confidence >= 99.0:
                        db.insert_contact({
                            "account_id": account_id_match,
                            "rep_id": REP_ID,
                            "name": contact.get("name"),
                            "title": contact.get("title"),
                            "email": contact.get("email"),
                            "phone": contact.get("phone"),
                            "linkedin_url": contact.get("linkedin_url"),
                            "raw_email_id": signal["id"],
                        })
                        inserted += 1
                        print(f"  ✓ [contacts] {contact.get('name')} → {best_match} (100%)")
                    else:
                        route_to_review_queue(
                            signal,
                            company_name or contact.get("name"),
                            best_match,
                            confidence,
                            "contacts email: needs review",
                        )
                        counts["review_queue"] += 1

                db.mark_signal_processed(signal["id"])
                counts["matched"] += inserted
                print(f"  ✓ [contacts] {inserted} contacts inserted")
                continue

            # ── Path A: CRM notification ──────────────────────────────────
            if source == "crm_notification":
                company_name, contact_name, signal_type, signal_body = extract_crm_signal(signal)
                if company_name:
                    summary_prompt = (
                        "You are a NetSuite sales intelligence assistant. "
                        "In 2 sentences: what happened and why it matters for a NetSuite rep.\n\n"
                        f"Signal: {signal_body}"
                    )
                    summary = _claude_text(client, summary_prompt, signal["id"], "signal_summary")
                    if contact_name:
                        summary = f"Contact: {contact_name}. " + summary

            # ── Path B: Screenshot forward ────────────────────────────────
            elif source == "screenshot_forward":
                image = _get_first_image(signal)
                if image:
                    image_b64, mime_type = image
                    result = _claude_vision(client, image_b64, mime_type, signal["id"])
                    company_name = result.get("company_name")
                    signal_type = result.get("signal_type") or "other"
                    what = result.get("what_happened") or ""
                    why = result.get("why_relevant") or ""
                    summary = f"{what} {why}".strip()
                    # Build a meaningful headline from extracted data instead of the screenshot filename
                    _stype_label = signal_type.replace("_", " ").title()
                    screenshot_headline = f"{company_name}: {_stype_label}" if company_name else _stype_label
                    # Outlook embeds Oracle branding images — if Vision returns our own company,
                    # the attachment isn't a real screenshot; fall back to subject line.
                    _oracle_names = {"oracle", "netsuite", "oracle netsuite", "oracle | netsuite"}
                    if (company_name or "").lower().strip() in _oracle_names:
                        company_name = None
                        source = "text_forward"
                else:
                    # No image found despite source detection — fall through to text
                    source = "text_forward"

            # ── Path C: Text forward ──────────────────────────────────────
            if source == "text_forward":
                subject = signal.get("subject") or ""
                body = (signal.get("body_text") or "")[:500]

                name_prompt = (
                    "Extract the company name from this email subject line. "
                    "Return only the company name, nothing else. "
                    "If you cannot identify a company name, return null.\n\n"
                    f"Subject: {subject}"
                )
                raw_name = _claude_text(client, name_prompt, signal["id"], "company_extraction")
                company_name = None if raw_name.lower() in ("null", "none", "") else raw_name

                type_prompt = (
                    f"Classify this email signal into exactly one of: {', '.join(SIGNAL_TYPES)}.\n"
                    "Return only the type string, nothing else.\n\n"
                    f"Subject: {subject}\nBody excerpt: {body}"
                )
                raw_type = _claude_text(client, type_prompt, signal["id"], "signal_type_classification")
                signal_type = raw_type.lower() if raw_type.lower() in SIGNAL_TYPES else "other"

                if company_name:
                    summary_prompt = (
                        "You are a NetSuite sales intelligence assistant. "
                        "Write a 2-3 sentence summary of this signal.\n"
                        "Answer: What is the signal? Why does it matter for a NetSuite sales rep?\n\n"
                        f"Subject: {subject}\nBody: {(signal.get('body_text') or '')[:1000]}"
                    )
                    summary = _claude_text(client, summary_prompt, signal["id"], "signal_summary")

            # ── NS record URL fallback ────────────────────────────────────
            # If no company name yet, check body for custjob.nl?id= and match directly
            if not company_name:
                body_text = signal.get("body_text") or ""
                ns_url_match = re.search(
                    r"nlcorp\.app\.netsuite\.com/app/common/entity/custjob\.nl\?id=(\d+)",
                    body_text, re.IGNORECASE
                )
                if ns_url_match:
                    ns_id = ns_url_match.group(1)
                    acct = db.get_account_by_ns_id(ns_id)
                    if acct:
                        company_name = acct["company_name"]
                        if not summary:
                            summary = f"CRM signal matched via NS record ID {ns_id}."
                        print(f"  ✓ [{source}] NS ID {ns_id} → {company_name!r} (direct match)")

            # ── Match + route ─────────────────────────────────────────────
            if not company_name:
                route_to_review_queue(signal, None, None, 0.0, "no company name found")
                counts["review_queue"] += 1
            else:
                account_id, best_match, confidence = match_account(company_name, account_names)

                if account_id:
                    write_matched_signal(
                        client, signal, account_id, company_name,
                        signal_type, confidence, summary, source,
                        headline=screenshot_headline,
                    )
                    counts["matched"] += 1
                    print(f"  ✓ [{source}] Matched {company_name!r} → {best_match!r} ({confidence:.0f}%)")
                else:
                    route_to_review_queue(
                        signal, company_name, best_match, confidence,
                        f"low confidence match ({confidence:.0f}%)"
                    )
                    counts["review_queue"] += 1
                    print(f"  ? [{source}] {company_name!r} → review queue ({confidence:.0f}%)")

            db.mark_signal_processed(signal["id"])

        except Exception as e:
            print(f"  ✗ Error processing signal {signal['id']}: {e}")
            counts["errors"] += 1

    return counts
