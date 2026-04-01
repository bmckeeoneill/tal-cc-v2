"""
One-pager generator for TCC — Claude-only, no external dependencies beyond anthropic.
Returns an HTML string ready for st.download_button.
"""

import json
import re
import datetime
import anthropic

from config import get_anthropic_key, MODEL

NETSUITE_LOGO_URL = "https://www.arin-innovation.com/wp-content/uploads/2022/09/Oracle-NetSuite-Portada.png"

REP_INFO = {
    "name": "Brian O'Neill",
    "title": "Senior Account Executive",
    "email": "brian.br.oneill@oracle.com",
    "phone": "(702) 306-1527",
}

PAGE_CSS = """
@page { size: Letter; margin: 0.5in; }
html, body { margin: 0; padding: 0; }

.page {
  width: 7.5in;
  height: 10in;
  overflow: hidden;
  box-sizing: border-box;
  background: #F4F7F8;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  display: flex;
  flex-direction: column;
}

.banner {
  height: 1.4in;
  min-height: 1.4in;
  max-height: 1.4in;
  display: grid;
  grid-template-columns: 5fr 1.4fr;
  column-gap: 0.2in;
  background: #2E4759;
  color: #F4F7F8;
  padding: 0.2in 0.25in;
  box-sizing: border-box;
}
.banner-left {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  overflow: hidden;
}
.company-name {
  font-size: 13px;
  font-weight: 800;
  font-style: italic;
  letter-spacing: 0.4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #AFC2D3;
}
.headline {
  margin-top: 4px;
  font-size: 17px;
  font-weight: 800;
  color: #D6B66A;
  line-height: 1.15;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.subheadline {
  margin-top: 5px;
  font-size: 10.5px;
  opacity: 0.9;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.banner-right {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  text-align: right;
  min-width: 0;
}
.ns-logo {
  max-width: 110px;
  max-height: 38px;
  object-fit: contain;
}
.contact {
  font-size: 9.5px;
  line-height: 1.35;
  opacity: 0.9;
}

.hear {
  background: #FFFFFF;
  padding: 0.15in 0.25in;
  box-sizing: border-box;
  border-bottom: 2px solid #AFC2D3;
}
.hear h2 {
  margin: 0 0 9px 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #425D73;
  text-transform: uppercase;
}
.hear-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.1in;
}
.hear-card {
  background: #F4F7F8;
  border: 1px solid #AFC2D3;
  border-left: 4px solid #2E4759;
  border-radius: 4px;
  padding: 0.1in 0.12in;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}
.hear-card-title {
  font-size: 12px;
  font-weight: 800;
  color: #2E4759;
  line-height: 1.2;
}
.hear-card-consequence {
  font-size: 9.5px;
  color: #425D73;
  line-height: 1.35;
}

.cso-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0.15in 0.25in 0.12in;
  box-sizing: border-box;
  overflow: hidden;
}
.cso-header {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.12in;
  margin-bottom: 0.07in;
}
.col-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 5px 10px;
  border-radius: 4px 4px 0 0;
  text-align: center;
}
.col-label.challenge { background: #2E4759; color: #F4F7F8; }
.col-label.solution  { background: #425D73; color: #F4F7F8; }
.col-label.outcome   { background: #D6B66A; color: #2E4759; }

.cso-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: repeat(4, 1fr);
  gap: 0.07in 0.12in;
  flex: 1;
}
.cso-cell {
  border-radius: 5px;
  padding: 0.09in 0.11in;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}
.cell-title {
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 4px;
  line-height: 1.2;
}
.cso-cell p {
  margin: 0;
  font-size: 9.5px;
  line-height: 1.35;
}
.cso-cell.challenge { background: #EEF2F5; border-left: 3px solid #2E4759; }
.cso-cell.challenge p, .cso-cell.challenge .cell-title { color: #2E4759; }
.cso-cell.solution  { background: #FFFFFF; border-left: 3px solid #425D73; }
.cso-cell.solution p { color: #2E4759; }
.cso-cell.solution .cell-title { color: #425D73; }
.cso-cell.outcome   { background: #FBF7EE; border-left: 3px solid #D6B66A; }
.cso-cell.outcome p { color: #2E4759; }
.cso-cell.outcome .cell-title { color: #8B6914; }

.roi-section {
  background: #2E4759;
  padding: 0.12in 0.25in;
  box-sizing: border-box;
}
.roi-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.08in;
}
.roi-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: #AFC2D3;
}
.roi-disclaimer {
  font-size: 8.5px;
  color: #AFC2D3;
  opacity: 0.7;
  font-style: italic;
}
.roi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.1in;
}
.roi-card {
  background: #3D5A6E;
  border-radius: 6px;
  padding: 0.1in 0.12in;
  box-sizing: border-box;
}
.roi-range {
  font-size: 16px;
  font-weight: 800;
  color: #D6B66A;
  line-height: 1.1;
  margin-bottom: 3px;
}
.roi-label {
  font-size: 9px;
  color: #AFC2D3;
  line-height: 1.3;
  margin-bottom: 7px;
  opacity: 0.9;
}
.roi-bullets {
  list-style: none;
  margin: 0;
  padding: 0;
}
.roi-bullets li {
  font-size: 9px;
  color: #F4F7F8;
  line-height: 1.3;
  padding-left: 10px;
  position: relative;
  margin-bottom: 3px;
}
.roi-bullets li::before {
  content: "›";
  position: absolute;
  left: 0;
  color: #D6B66A;
  font-weight: 700;
}

.bottom-band {
  height: 0.9in;
  min-height: 0.9in;
  max-height: 0.9in;
  background: #2E4759;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.35in;
  box-sizing: border-box;
}
.cta {
  font-size: 13px;
  font-weight: 700;
  color: #D6B66A;
  text-align: center;
  line-height: 1.4;
}
.cta span {
  display: block;
  font-size: 10px;
  font-weight: 400;
  color: #AFC2D3;
  margin-top: 4px;
}
"""

_GENERATION_PROMPT = """You are a NetSuite B2B sales copywriter building a one-pager for a prospect company.

Company: {company_name}
Industry: {industry}
Location: {city_state}
Website: {domain}
Tech stack (current systems): {tech_stack}
Recent signals / notes about this account:
{signals_and_notes}

Return a single valid JSON object with exactly these keys. No markdown fences. No extra text.

{{
  "headline": "One punchy line, 7 words max. No em dashes. No filler.",
  "subheadline": "One sentence, 12-20 words, connecting their business model to what NetSuite fixes. No em dashes.",
  "hear_bullets": [
    {{"title": "Short bold pain point, 4-7 words, no -ing verb endings", "consequence": "One sentence: what goes wrong because of this, specific to their vertical"}},
    {{"title": "...", "consequence": "..."}},
    {{"title": "...", "consequence": "..."}},
    {{"title": "...", "consequence": "..."}}
  ],
  "triplets": [
    {{
      "challenge_title": "2-4 word label",
      "challenge": "One sentence, specific to their vertical, no em dashes",
      "solution_title": "2-4 word label",
      "solution": "One sentence, what NetSuite does, concrete, no buzzwords",
      "outcome_title": "2-4 word result label",
      "outcome": "One sentence, tangible metric or business impact"
    }},
    {{"challenge_title": "...", "challenge": "...", "solution_title": "...", "solution": "...", "outcome_title": "...", "outcome": "..."}},
    {{"challenge_title": "...", "challenge": "...", "solution_title": "...", "solution": "...", "outcome_title": "...", "outcome": "..."}},
    {{"challenge_title": "...", "challenge": "...", "solution_title": "...", "solution": "...", "outcome_title": "...", "outcome": "..."}}
  ],
  "roi": {{
    "time_savings": {{
      "range": "e.g. 15-25% or $80K-$150K",
      "label": "Reduction in manual finance and ops labor",
      "bullets": ["6-10 word outcome", "6-10 word outcome", "6-10 word outcome"]
    }},
    "working_capital": {{
      "range": "e.g. 5-15%",
      "label": "Improvement in working capital management",
      "bullets": ["6-10 word outcome", "6-10 word outcome", "6-10 word outcome"]
    }},
    "system_consolidation": {{
      "range": "e.g. 20-35%",
      "label": "Reduction in IT overhead and system costs",
      "bullets": ["6-10 word outcome", "6-10 word outcome", "6-10 word outcome"]
    }}
  }}
}}

Rules:
- No em dashes anywhere.
- No buzzwords: leverage, synergy, streamline, robust, scalable, cutting-edge.
- ROI ranges should be conservative (low end), sized for a company in this industry.
- Make everything specific to {industry} — not generic ERP copy.
- Return only valid JSON.
"""


def _generate_content(acct: dict, signals: list, notes: list) -> dict:
    city_state = ", ".join(p for p in [acct.get("city"), acct.get("state")] if p) or "—"
    tech_stack = ", ".join(acct.get("tech_stack") or []) or "Unknown"
    domain = acct.get("domain") or "—"

    sig_lines = []
    for s in signals[:10]:
        date = (s.get("signal_date") or "")[:10]
        sig_lines.append(f"  [{date}] [{s.get('signal_type','')}] {s.get('headline','')}: {s.get('summary','')}")
    for n in notes[:5]:
        date = (n.get("created_at") or "")[:10]
        sig_lines.append(f"  [{date}] [note] {n.get('note_text','')}")
    signals_and_notes = "\n".join(sig_lines) if sig_lines else "None on file."

    prompt = _GENERATION_PROMPT.format(
        company_name=acct.get("company_name", ""),
        industry=acct.get("industry") or "—",
        city_state=city_state,
        domain=domain,
        tech_stack=tech_stack,
        signals_and_notes=signals_and_notes,
    )

    cl = anthropic.Anthropic(api_key=get_anthropic_key())
    resp = cl.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw).strip()
    raw = re.sub(r"\s*```\s*$", "", raw).strip()

    data = json.loads(raw)

    # Pad to 4 triplets if needed
    triplets = data.get("triplets", [])[:4]
    while len(triplets) < 4:
        triplets.append({"challenge_title": "", "challenge": "", "solution_title": "", "solution": "", "outcome_title": "", "outcome": ""})
    data["triplets"] = triplets

    hear = data.get("hear_bullets", [])[:4]
    while len(hear) < 4:
        hear.append({"title": "", "consequence": ""})
    data["hear_bullets"] = hear

    return data


def _build_html(company_name: str, data: dict) -> str:
    rep = REP_INFO

    # Banner
    banner = f"""
<div class="banner">
  <div class="banner-left">
    <div class="company-name">{company_name}</div>
    <div class="headline">{data['headline']}</div>
    <div class="subheadline">{data['subheadline']}</div>
  </div>
  <div class="banner-right">
    <img class="ns-logo" src="{NETSUITE_LOGO_URL}" alt="NetSuite logo">
    <div class="contact">{rep['name']}<br>{rep['title']}<br>{rep['email']}<br>{rep['phone']}</div>
  </div>
</div>"""

    # Hear section
    hear_cards = "".join(
        f'<div class="hear-card"><div class="hear-card-title">{b["title"]}</div>'
        f'<div class="hear-card-consequence">{b["consequence"]}</div></div>'
        for b in data["hear_bullets"]
    )
    hear = f"""
<div class="hear">
  <h2>What we hear from companies like yours</h2>
  <div class="hear-grid">{hear_cards}</div>
</div>"""

    # CSO grid
    cells = "".join(
        f'<div class="cso-cell challenge"><div class="cell-title">{t["challenge_title"]}</div><p>{t["challenge"]}</p></div>'
        f'<div class="cso-cell solution"><div class="cell-title">{t["solution_title"]}</div><p>{t["solution"]}</p></div>'
        f'<div class="cso-cell outcome"><div class="cell-title">{t["outcome_title"]}</div><p>{t["outcome"]}</p></div>'
        for t in data["triplets"]
    )
    cso = f"""
<div class="cso-section">
  <div class="cso-header">
    <div class="col-label challenge">Challenge</div>
    <div class="col-label solution">NetSuite Solution</div>
    <div class="col-label outcome">Outcome</div>
  </div>
  <div class="cso-grid">{cells}</div>
</div>"""

    # ROI
    def roi_card(key):
        d = data["roi"].get(key, {})
        bullets_html = "".join(f"<li>{b}</li>" for b in (d.get("bullets") or [])[:3])
        return (
            f'<div class="roi-card">'
            f'<div class="roi-range">{d.get("range","")}</div>'
            f'<div class="roi-label">{d.get("label","")}</div>'
            f'<ul class="roi-bullets">{bullets_html}</ul>'
            f'</div>'
        )

    roi = f"""
<div class="roi-section">
  <div class="roi-header">
    <div class="roi-title">Financial Impact of Moving to NetSuite</div>
    <div class="roi-disclaimer">Industry average estimates only</div>
  </div>
  <div class="roi-grid">
    {roi_card("time_savings")}
    {roi_card("working_capital")}
    {roi_card("system_consolidation")}
  </div>
</div>"""

    bottom = f"""
<div class="bottom-band">
  <div class="cta">
    Open to 15 minutes next week to map this to your current process?
    <span>{rep['name']} &nbsp;|&nbsp; {rep['email']} &nbsp;|&nbsp; {rep['phone']}</span>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>{PAGE_CSS}</style>
</head>
<body>
<div class="page">
  {banner}
  {hear}
  {cso}
  {roi}
  {bottom}
</div>
</body>
</html>"""


def generate_one_pager(acct: dict, signals: list, notes: list) -> str:
    """Generate a one-pager HTML string for the given account. Raises on failure."""
    data = _generate_content(acct, signals, notes)
    company_name = acct.get("company_name", "")
    # Strip leading numeric IDs (e.g. "1141930 Christy Sports" -> "Christy Sports")
    company_name = re.sub(r"^\d{6,}\s+", "", company_name).strip()
    return _build_html(company_name, data)
