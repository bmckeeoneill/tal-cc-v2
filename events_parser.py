"""
Events parser for TAL Command Center.

Parses MMTT-style event digest emails and writes events + account_events to Supabase.
Called by signal_processor.py when source = 'events_digest'.

Email structure expected:
  Sections: Evergreen, Competitive, Upcoming In-Person Events
  In-person has region sub-headers (Central, Florida, Texas, etc.)
  Each event line: DATE - EVENT NAME<URL> - Seismic Page<URL>
"""

import re
from datetime import date, datetime
from typing import Optional

import db

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


def _infer_year(month: int, day: int) -> int:
    today = date.today()
    if month < today.month or (month == today.month and day < today.day):
        return today.year + 1
    return today.year


def _parse_date(date_str: str) -> Optional[date]:
    """Parse dates like '3/25', '03/25', '3/25/2025', '3 /4'."""
    date_str = re.sub(r"\s", "", date_str.strip())  # remove any spaces
    parts = date_str.split("/")
    try:
        if len(parts) == 2:
            month, day = int(parts[0]), int(parts[1])
            year = _infer_year(month, day)
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


def parse_events_email(body: str, raw_email_id: Optional[str] = None) -> list[dict]:
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

            event_date = _parse_date(date_str)
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


def process_events_email(signal: dict) -> int:
    """
    Parse signal body, write events + account_events.
    Returns count of events inserted.
    """
    body = signal.get("body_text") or ""
    raw_email_id = signal.get("id")

    parsed = parse_events_email(body, raw_email_id)
    if not parsed:
        print(f"  [events] No events parsed from signal {raw_email_id}")
        return 0

    # Load all accounts once
    client = db.get_client()
    all_accounts = client.table("accounts").select("id, company_name, state").eq("rep_id", "brianoneill").execute().data or []

    inserted = 0
    for event in parsed:
        event_id = db.insert_event(event)
        if not event_id:
            continue  # duplicate, skipped
        inserted += 1

        matches = _accounts_for_event(event, all_accounts)
        if matches:
            rows = [{"account_id": aid, "event_id": event_id, "match_reason": reason}
                    for aid, reason in matches]
            # Insert in batches, ignore conflicts
            try:
                client.table("account_events").upsert(rows, on_conflict="account_id,event_id").execute()
            except Exception as e:
                print(f"  [events] account_events insert error: {e}")

    print(f"  [events] {inserted} new events written, matched to accounts")
    return inserted
