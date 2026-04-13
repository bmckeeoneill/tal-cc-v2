"""
Events parser for TAL Command Center.

Parses MMTT-style event digest emails and writes events + account_events to Supabase.
Called by signal_processor.py when source = 'events_digest'.

Email structure expected:
  Sections: Evergreen, Competitive, Upcoming In-Person Events
  In-person has region sub-headers (Central, Florida, Texas, etc.)
  Each event line: DATE - EVENT NAME<URL> - Seismic Page<URL>
"""

import json
import re
from datetime import date, datetime
from typing import Optional

import db
from config import get_anthropic_key, MODEL

# State abbreviation → full name mapping for location matching
STATE_ABBR = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming",
}

# Region keywords → states they cover
REGION_STATES = {
    "florida":    {"FL"},
    "texas":      {"TX"},
    "central":    {"IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"},
    "northeast":  {"CT", "DE", "ME", "MD", "MA", "NH", "NJ", "NY", "PA", "RI", "VT"},
    "southeast":  {"AL", "AR", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "VA", "WV"},
    "west":       {"AK", "AZ", "CA", "CO", "HI", "ID", "MT", "NV", "NM", "OR", "UT", "WA", "WY"},
    "southwest":  {"AZ", "CO", "NM", "OK", "TX", "UT"},
    "mid-atlantic": {"DE", "MD", "NJ", "NY", "PA", "VA"},
    "mountain":   {"AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY"},
    "pacific":    {"AK", "CA", "HI", "OR", "WA"},
}


def _infer_year(month: int, day: int, ref: Optional[date] = None) -> int:
    """Infer year for a month/day relative to ref date (defaults to today).
    If the resulting date is more than 60 days before ref, assume next year.
    This prevents bumping events to +1 year just because the email arrived
    a few days after the event month rolled over.
    """
    from datetime import timedelta
    ref = ref or date.today()
    candidate = date(ref.year, month, day)
    if (ref - candidate).days > 60:
        return ref.year + 1
    return ref.year


def _parse_date(date_str: str, ref: Optional[date] = None) -> Optional[date]:
    """Parse dates like '3/25', '03/25', '3/25/2025', '3 /4'."""
    date_str = re.sub(r"\s", "", date_str.strip())  # remove any spaces
    parts = date_str.split("/")
    try:
        if len(parts) == 2:
            month, day = int(parts[0]), int(parts[1])
            year = _infer_year(month, day, ref)
            return date(year, month, day)
        elif len(parts) == 3:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            if year < 100:
                year += 2000
            return date(year, month, day)
    except (ValueError, TypeError):
        pass
    return None


def _extract_urls(text: str) -> list[str]:
    return re.findall(r'https?://[^\s<>"]+', text)


def _classify_url(url: str) -> str:
    """Returns 'registration', 'seismic', or 'other'."""
    if "seismic.com" in url:
        return "seismic"
    if "nlcorp" in url or "netsuite" in url or "oracle" in url:
        return "registration"
    return "other"


def parse_events_email(body: str, raw_email_id: Optional[str] = None, ref: Optional[date] = None) -> list[dict]:
    """
    Parse an MMTT-style events digest email body.
    Returns list of event dicts ready for insert_event().
    """
    events = []
    current_section = None   # evergreen | competitive | in_person
    current_region = None

    section_patterns = {
        "industry":     re.compile(r"^industry\s*$", re.IGNORECASE),
        "evergreen":    re.compile(r"^evergreen\s*$", re.IGNORECASE),
        "competitive":  re.compile(r"^competitive\s*$", re.IGNORECASE),
        "in_person":    re.compile(r"upcoming in.person events?", re.IGNORECASE),
    }

    # Strip bullet prefix (e.g. "  *   ", "* ") then match: "3/25 - Event..."
    # Also handles spaces in dates like "3 /4" and em-dashes
    bullet_re = re.compile(r"^\s*\*\s*")
    event_line_re = re.compile(r"^(\d{1,2}\s*/\s*\d{1,2}(?:\s*/\s*\d{2,4})?)\s*[-–]\s*(.+)$")

    for raw_line in body.splitlines():
        # Strip bullet prefix before processing
        line = bullet_re.sub("", raw_line).strip()
        if not line:
            continue

        # Section header detection
        matched_section = None
        for sec, pat in section_patterns.items():
            if pat.search(line):
                matched_section = sec
                break
        if matched_section:
            current_section = matched_section
            current_region = None
            continue

        # Inside in_person: check for region sub-headers (short lines, no date prefix, no URL)
        if current_section == "in_person" and not event_line_re.match(line) and not _extract_urls(line):
            # Heuristic: a region header is a short line (≤40 chars) with no numbers
            if len(line) <= 40 and not re.search(r"\d", line):
                current_region = line.strip()
                continue

        # Event line
        m = event_line_re.match(line)
        if m and current_section:
            date_str = m.group(1)
            rest = m.group(2)

            event_date = _parse_date(date_str, ref)
            if not event_date:
                continue

            # Extract URLs
            urls = _extract_urls(rest)
            reg_url = next((u for u in urls if _classify_url(u) == "registration"), None)
            seismic_url = next((u for u in urls if _classify_url(u) == "seismic"), None)

            # Strip URLs and separators to get clean event name
            name = re.sub(r'https?://[^\s<>"]+', "", rest)
            name = re.sub(r'\s*[-–|]\s*Seismic\s*(Page)?\s*', " ", name, flags=re.IGNORECASE)
            name = re.sub(r'[<>]', "", name)
            name = " ".join(name.split()).strip(" -–|")

            if not name:
                continue

            # Determine event type
            if current_section in ("evergreen", "industry"):
                event_type = "evergreen"
            elif current_section == "competitive":
                event_type = "competitive"
            elif "webinar" in name.lower():
                event_type = "webinar"
            else:
                event_type = "in_person"

            events.append({
                "event_name": name,
                "event_date": event_date.isoformat(),
                "event_type": event_type,
                "region": current_region if current_section == "in_person" else None,
                "registration_url": reg_url,
                "seismic_url": seismic_url,
                "raw_email_id": raw_email_id,
            })

    return events


def _accounts_for_event(event: dict, all_accounts: list[dict]) -> list[tuple[str, str]]:
    """
    Returns list of (account_id, match_reason) for an event.
    """
    event_type = event.get("event_type")
    region = (event.get("region") or "").lower()

    # Webinars, evergreen, competitive → all accounts
    if event_type in ("webinar", "evergreen", "competitive"):
        return [(a["id"], "webinar_all") for a in all_accounts]

    # In-person → match by region/state
    if not region:
        return [(a["id"], "webinar_all") for a in all_accounts]

    # Build set of matching state abbreviations
    matching_states = set()

    # Direct state name match
    for abbr, full in STATE_ABBR.items():
        if region in full or full in region:
            matching_states.add(abbr)

    # Region keyword match
    for reg_key, states in REGION_STATES.items():
        if reg_key in region or region in reg_key:
            matching_states.update(states)

    # If region IS a state name directly
    if not matching_states:
        matching_states.add(region.upper()[:2])

    matched = []
    for a in all_accounts:
        acct_state = (a.get("state") or "").upper().strip()
        if acct_state in matching_states:
            matched.append((a["id"], "location_match"))

    return matched


def _parse_events_with_claude(body: str, raw_email_id: Optional[str] = None, ref: Optional[date] = None) -> list[dict]:
    """
    Fallback: use Claude to extract events from an unstructured email body.
    Returns same list-of-dicts shape as parse_events_email().
    """
    import anthropic
    ref_str = (ref or date.today()).isoformat()
    prompt = (
        f"The email below was received on {ref_str}. Extract all events from it.\n\n"
        "Return a JSON array. Each object must have these fields:\n"
        "  event_name (string)\n"
        "  event_date (YYYY-MM-DD — use the email received date as reference; only push to next year if the date is more than 60 days before the received date)\n"
        "  event_type (one of: webinar, in_person, evergreen, competitive)\n"
        "  region (string or null — only for in_person events, e.g. 'Texas', 'Central')\n"
        "  registration_url (string or null)\n"
        "  seismic_url (string or null)\n\n"
        "Return only the JSON array, no explanation.\n\n"
        f"EMAIL:\n{body}"
    )
    import db as _db
    from config import DAILY_AI_CALL_BUDGET
    if _db.get_today_ai_call_count() >= DAILY_AI_CALL_BUDGET:
        print("  [events] Daily Claude budget exhausted — skipping event extraction")
        return []
    client = anthropic.Anthropic(api_key=get_anthropic_key())
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [events] Claude fallback returned unparseable JSON: {raw[:200]}")
        return []

    events = []
    for item in items:
        if not item.get("event_name") or not item.get("event_date"):
            continue
        events.append({
            "event_name": item["event_name"],
            "event_date": item["event_date"],
            "event_type": item.get("event_type") or "webinar",
            "region": item.get("region"),
            "registration_url": item.get("registration_url"),
            "seismic_url": item.get("seismic_url"),
            "raw_email_id": raw_email_id,
        })
    return events


def process_events_email(signal: dict) -> int:
    """
    Parse signal body with Claude, write unconfirmed events.
    User reviews and confirms in the Events page before they fan out to accounts.
    Returns count of events inserted.
    """
    body = signal.get("body_text") or ""
    raw_email_id = signal.get("id")

    ref = None
    received_at = signal.get("received_at")
    if received_at:
        try:
            ref = date.fromisoformat(received_at[:10])
        except ValueError:
            pass

    # Always use Claude — handles any format
    parsed = _parse_events_with_claude(body, raw_email_id, ref)
    if not parsed:
        print(f"  [events] No events parsed from signal {raw_email_id}")
        return 0

    inserted = 0
    for event in parsed:
        # Mark as unconfirmed — user reviews in Events page
        event["confirmed"] = False
        event_id = db.insert_event(event)
        if not event_id:
            continue  # duplicate
        inserted += 1

    print(f"  [events] {inserted} new suggested events written (pending review)")
    return inserted
