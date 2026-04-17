"""Account detail page."""
import os
import datetime
import streamlit as st
import anthropic as _anthropic

import db
from db import get_account
from config import get_anthropic_key as _get_anthropic_key, MODEL, REP_ID
from pages._shared import go, back_btn
import content_utils

_OUTREACH_TONE = (
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


def render():
    st.markdown("<script>window.scrollTo(0, 0);</script>", unsafe_allow_html=True)
    back_btn("← Back to TAL", "tal")

    account_id = st.session_state.get("selected_account")
    if not account_id:
        st.warning("No account selected.")
        return

    acct = get_account(account_id)
    if not acct:
        st.error(f"Account {account_id} not found.")
        return

    _starred = acct.get("starred") or False
    _star_label = "★ Starred" if _starred else "☆ Star"
    _chop = acct.get("chop_block") or False
    _chop_label = "🪓 On Chop Block" if _chop else "🪓 Chop Block"
    _star_cols = st.columns([4, 1.2, 1.5])
    with _star_cols[0]:
        st.markdown(f"## {acct.get('company_name', 'Unknown')}")
    with _star_cols[1]:
        if st.button(_star_label, key=f"star_toggle_{account_id}",
                     type="primary" if _starred else "secondary"):
            db.toggle_starred(account_id, not _starred)
            st.rerun()
    with _star_cols[2]:
        if st.button(_chop_label, key=f"chop_toggle_{account_id}",
                     type="primary" if _chop else "secondary",
                     help="Mark for removal from TAL"):
            db.toggle_chop_block(account_id, not _chop)
            st.rerun()

    col1, col2 = st.columns(2)

    with col1:
        for label, val in [
            ("Industry",   acct.get("industry") or "—"),
            ("State",      acct.get("state") or "—"),
            ("City",       acct.get("city") or "—"),
            ("Sales Rep",  acct.get("sales_rep") or "—"),
        ]:
            st.markdown(f'<div class="account-section-label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value">{val}</div>', unsafe_allow_html=True)
            st.write("")

        # SDR field
        sdr_name = acct.get("sdr_name") or ""
        sdr_assigned = (acct.get("sdr_assigned_at") or "")[:10]
        st.markdown('<div class="account-section-label">SDR</div>', unsafe_allow_html=True)
        sdr_edit_key = f"sdr_edit_{account_id}"
        if st.session_state.get(sdr_edit_key):
            new_sdr = st.text_input("SDR name", value=sdr_name, key=f"sdr_input_{account_id}", label_visibility="collapsed")
            sc1, sc2 = st.columns(2)
            with sc1:
                if st.button("Save SDR", key=f"sdr_save_{account_id}"):
                    if new_sdr.strip():
                        db.update_sdr(account_id, new_sdr.strip())
                    st.session_state[sdr_edit_key] = False
                    st.rerun()
            with sc2:
                if st.button("Cancel", key=f"sdr_cancel_{account_id}"):
                    st.session_state[sdr_edit_key] = False
                    st.rerun()
        else:
            sdr_display = f"{sdr_name} (assigned {sdr_assigned})" if sdr_name else "—"
            st.markdown(f'<div class="account-section-value">{sdr_display}</div>', unsafe_allow_html=True)
            sdr_btn_col, sdr_clr_col = st.columns(2)
            with sdr_btn_col:
                if st.button("Edit SDR", key=f"sdr_edit_btn_{account_id}"):
                    st.session_state[sdr_edit_key] = True
                    st.rerun()
            if sdr_name:
                with sdr_clr_col:
                    if st.button("Clear SDR", key=f"sdr_clear_{account_id}"):
                        db.clear_sdr(account_id)
                        st.rerun()
        st.write("")

        # Tech stack field
        st.markdown('<div class="account-section-label">Tech Stack</div>', unsafe_allow_html=True)
        ts_edit_key = f"ts_edit_{account_id}"
        current_ts = acct.get("tech_stack") or []
        if st.session_state.get(ts_edit_key):
            ts_working_key = f"ts_working_{account_id}"
            if ts_working_key not in st.session_state:
                st.session_state[ts_working_key] = list(current_ts)
            working = st.session_state[ts_working_key]
            for i, item in enumerate(working):
                ic1, ic2 = st.columns([4, 1])
                with ic1:
                    st.write(item)
                with ic2:
                    if st.button("✕", key=f"ts_remove_{account_id}_{i}"):
                        working.pop(i)
                        st.rerun()
            new_item = st.text_input("Add system", key=f"ts_add_{account_id}", label_visibility="collapsed",
                                     placeholder="e.g. Odoo, QuickBooks...")
            tc1, tc2 = st.columns(2)
            with tc1:
                if st.button("Add", key=f"ts_add_btn_{account_id}") and new_item.strip():
                    working.append(new_item.strip())
                    st.rerun()
            with tc2:
                if st.button("Save Tech Stack", key=f"ts_save_{account_id}"):
                    old_set = set(current_ts)
                    new_set = set(working)
                    added = new_set - old_set
                    removed = old_set - new_set
                    db.update_tech_stack(account_id, working)
                    if added or removed:
                        parts = []
                        if added: parts.append(f"added {', '.join(sorted(added))}")
                        if removed: parts.append(f"removed {', '.join(sorted(removed))}")
                        db.save_note(account_id, f"Tech stack updated: {'; '.join(parts)}.")
                    st.session_state[ts_edit_key] = False
                    del st.session_state[ts_working_key]
                    st.rerun()
        else:
            if current_ts:
                st.markdown(f'<div class="account-section-value">{", ".join(current_ts)}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="account-section-value">—</div>', unsafe_allow_html=True)
            if st.button("Edit Tech Stack", key=f"ts_edit_btn_{account_id}"):
                st.session_state[ts_edit_key] = True
                st.rerun()
        st.write("")

    with col2:
        domain = acct.get("domain") or ""
        if domain:
            st.markdown(f'<div class="account-section-label">Website</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value"><a href="https://{domain}" target="_blank">{domain}</a></div>', unsafe_allow_html=True)
            st.write("")

        li_url = acct.get("linkedin_url") or ""
        if li_url:
            st.markdown(f'<div class="account-section-label">LinkedIn</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value"><a href="{li_url}" target="_blank">View Company</a></div>', unsafe_allow_html=True)
            st.write("")

        ns_url = acct.get("nscorp_url") or ""
        if ns_url:
            st.markdown(f'<div class="account-section-label">NetSuite</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="account-section-value"><a href="{ns_url}" target="_blank">Open in NetSuite</a></div>', unsafe_allow_html=True)
            st.write("")

    st.divider()

    # ── Lead Highlight ────────────────────────────────────────────────────────
    lh_key = f"lead_highlight_{account_id}"
    if lh_key not in st.session_state:
        st.session_state[lh_key] = db.get_lead_highlight(account_id) or ""
    with st.expander("Lead Highlight", expanded=bool(st.session_state.get(lh_key))):
        lh_cols = st.columns([5, 1, 1])
        with lh_cols[0]:
            lh_text = st.text_area(
                "Lead Highlight",
                value=st.session_state[lh_key],
                height=80,
                key=f"lh_text_{account_id}",
                label_visibility="collapsed",
                placeholder="Why should the SDR work this account? Auto-generate or write your own.",
            )
        with lh_cols[1]:
            if st.button("Save", key=f"lh_save_{account_id}"):
                db.save_lead_highlight(account_id, lh_text)
                st.session_state[lh_key] = lh_text
                st.rerun()
        with lh_cols[2]:
            if st.button("Generate", key=f"lh_gen_{account_id}"):
                with st.spinner("Generating..."):
                    _sigs = db.get_signals_for_account(account_id, days=365)
                    _sig_text = "\n".join(
                        f"[{s.get('signal_type','')}] {s.get('headline','')} — {s.get('summary','')}"
                        for s in _sigs[:10]
                    ) or "No signals available."
                    _lh_prompt = (
                        "You are a NetSuite sales rep writing a personal note to your SDR about why they should work this account.\n\n"
                        "Write 2-3 short sentences in first person, as if Brian is talking directly to the SDR. "
                        "Be specific about what makes this account worth pursuing right now. "
                        "Reference signals if available. Sound like a rep who is genuinely excited about the opportunity, not a marketer.\n\n"
                        "Rules:\n"
                        "- First person, conversational — \"I've been watching these guys\" not \"this company presents an opportunity\"\n"
                        "- No marketing language, no ICP references, no em dashes\n"
                        "- Short sentences only\n"
                        "- Specific beats generic — mention what you actually see, not what could theoretically be true\n\n"
                        f"Company: {acct.get('company_name','')}\n"
                        f"Industry: {acct.get('industry') or 'unknown'}\n"
                        f"NAICS: {acct.get('naics_description') or ''}\n"
                        f"What they do: {acct.get('naics_notes') or ''}\n"
                        f"Signals:\n{_sig_text}"
                    )
                    _cl = _anthropic.Anthropic(api_key=_get_anthropic_key())
                    _resp = _cl.messages.create(model=MODEL, max_tokens=256,
                                                messages=[{"role": "user", "content": _lh_prompt}])
                    _lh_result = _resp.content[0].text.strip()
                    db.log_ai_call({"rep_id": REP_ID, "call_type": "lead_highlight",
                                    "prompt_used": _lh_prompt, "model_version": MODEL,
                                    "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
                    db.save_lead_highlight(account_id, _lh_result)
                    st.session_state[lh_key] = _lh_result
                    st.rerun()

    # ── Contacts ──────────────────────────────────────────────────────────────
    contacts = db.get_contacts_for_account(account_id)
    _contact_header = f"Contacts ({len(contacts)})" if contacts else "Contacts"
    with st.expander(_contact_header, expanded=False):
        if contacts:
            for c in contacts:
                cell_star = " ★" if c.get("cell_confirmed") else ""
                phone_str = (c.get("phone") or "") + cell_star if c.get("phone") else None
                _cparts = [p for p in [c.get("name"), c.get("title"), c.get("email"), phone_str] if p]
                li = c.get("linkedin_url")
                row_text = " · ".join(_cparts)
                if li:
                    st.markdown(f"{row_text} — [LinkedIn]({li})")
                else:
                    st.markdown(row_text or "—")
            st.divider()

        # ── Paste ingester ────────────────────────────────────────────────────
        st.caption("Paste anything — email signature, LinkedIn profile, name and number — and Claude will extract the contacts.")
        _paste_key = f"contact_paste_{account_id}"
        _parsed_key = f"contact_parsed_{account_id}"
        st.text_area("Paste contact info", key=_paste_key,
                     label_visibility="collapsed",
                     placeholder="John Smith, VP Sales, john@acme.com, 303-555-1234...")
        if st.button("Parse Contacts", key=f"parse_contacts_{account_id}"):
            _raw_text = st.session_state.get(_paste_key, "")
            if _raw_text.strip():
                with st.spinner("Parsing..."):
                    try:
                        _cl = _anthropic.Anthropic(api_key=_get_anthropic_key())
                        _parse_prompt = (
                            "Extract all contacts from the text below. Return a JSON array of objects with these keys: "
                            "name, title, email, phone, linkedin_url. Use null for missing fields. "
                            "Return only valid JSON, no explanation.\n\n"
                            f"Text:\n{_raw_text.strip()}"
                        )
                        _pr = _cl.messages.create(model=MODEL, max_tokens=512,
                                                  messages=[{"role": "user", "content": _parse_prompt}])
                        import json as _json2
                        _raw_resp = _pr.content[0].text.strip()
                        # Strip markdown code fences if present
                        if _raw_resp.startswith("```"):
                            _raw_resp = _raw_resp.split("\n", 1)[-1]
                            _raw_resp = _raw_resp.rsplit("```", 1)[0].strip()
                        elif _raw_resp.startswith("json\n"):
                            _raw_resp = _raw_resp[5:].strip()
                        _parsed = _json2.loads(_raw_resp)
                        st.session_state[_parsed_key] = _parsed if isinstance(_parsed, list) else [_parsed]
                    except Exception as _e:
                        st.error(f"Parse failed: {_e}")
            else:
                st.warning("Paste some contact info first.")

        _parsed_contacts = st.session_state.get(_parsed_key, [])
        if _parsed_contacts:
            st.markdown("**Parsed — confirm to save:**")
            for _i, _pc in enumerate(_parsed_contacts):
                _pc_parts = [p for p in [_pc.get("name"), _pc.get("title"), _pc.get("email"), _pc.get("phone")] if p]
                st.write(" · ".join(_pc_parts) or "—")
                if _pc.get("linkedin_url"):
                    st.caption(_pc["linkedin_url"])
            if st.button("Save All", key=f"save_parsed_{account_id}", type="primary"):
                for _pc in _parsed_contacts:
                    db.insert_contact({
                        "account_id": account_id,
                        "rep_id": REP_ID,
                        "confirmed": True,
                        "name": _pc.get("name"),
                        "title": _pc.get("title"),
                        "email": _pc.get("email"),
                        "phone": _pc.get("phone"),
                        "linkedin_url": _pc.get("linkedin_url"),
                    })
                del st.session_state[_parsed_key]
                st.rerun()
    st.write("")

    # ── Industry Brief ────────────────────────────────────────────────────────
    with st.expander("Why NetSuite — Industry Brief"):
        brief_key = f"industry_brief_{account_id}"
        existing_brief = st.session_state.get(brief_key)
        if existing_brief:
            st.markdown(existing_brief)
            if st.button("Regenerate", key=f"regen_brief_{account_id}"):
                del st.session_state[brief_key]
                st.rerun()
        else:
            industry = acct.get("industry") or ""
            ts_list = acct.get("tech_stack") or []
            if st.button("Generate Industry Brief", key=f"gen_brief_{account_id}"):
                with st.spinner("Generating..."):
                    brief_prompt = (
                        "You are a NetSuite sales rep who knows this industry well. "
                        "Write 3-5 short bullet points explaining why companies in this industry are moving to NetSuite.\n\n"
                        f"Company: {acct.get('company_name', '')}\n"
                        f"Industry: {industry or 'unknown'}\n"
                        f"Current systems (if known): {', '.join(ts_list) or 'unknown'}\n\n"
                        "Focus on:\n"
                        "- The specific pain points NetSuite solves for this industry\n"
                        "- What they are typically replacing (QuickBooks, Sage, spreadsheets, etc.)\n"
                        "- The business triggers that drive the move (growth, complexity, multi-entity, inventory, etc.)\n\n"
                        "Rules:\n"
                        "- No marketing language\n"
                        "- Short bullets, one idea each\n"
                        "- Write like a rep who knows the space from field experience, not a brochure\n"
                        "- 3-5 bullets only"
                    )
                    _cl = _anthropic.Anthropic(api_key=_get_anthropic_key())
                    resp = _cl.messages.create(
                        model=MODEL, max_tokens=400,
                        messages=[{"role": "user", "content": brief_prompt}]
                    )
                    brief_text = resp.content[0].text.strip()
                    db.log_ai_call({"rep_id": REP_ID, "call_type": "industry_brief",
                                    "prompt_used": brief_prompt, "model_version": MODEL,
                                    "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
                    st.session_state[brief_key] = brief_text
                    st.rerun()
            else:
                st.caption(f"Industry: {industry or '—'}")

    # ── Signals ───────────────────────────────────────────────────────────────
    with st.expander("Insights & Signals", expanded=True):
        signals = db.get_signals_for_account(account_id, days=30)
        if not signals:
            st.caption("No signals in the last 30 days.")
        else:
            for s in signals:
                st.markdown(f"**{s.get('headline') or '—'}**")
                st.caption(f"{s.get('signal_type', '').replace('_', ' ').title()} · {(s.get('signal_date') or '')[:10]} · {s.get('match_confidence', 0):.0f}% confidence")
                if s.get("summary"):
                    st.write(s["summary"])
                if s.get("file_url"):
                    st.markdown(f"[📎 View attachment]({s['file_url']})")
                st.markdown("---")

    # ── Weekly Analysis (hidden — logic preserved) ───────────────────────────
    if False:  # noqa — keep logic, not exposed in UI
     with st.expander("Weekly Analysis"):
        analysis_resp = (
            db.get_client()
            .table("weekly_analysis")
            .select("week_of, summary, trend, model_version")
            .eq("account_id", account_id)
            .order("week_of", desc=True)
            .limit(4)
            .execute()
        )
        analyses = analysis_resp.data or []
        if not analyses:
            st.caption("No analysis generated yet.")
        else:
            for a in analyses:
                trend = (a.get("trend") or "flat").upper()
                trend_icon = {"HEATING": "🔥", "COOLING": "❄️", "FLAT": "➡️"}.get(trend, "➡️")
                st.markdown(f"**Week of {a.get('week_of')}** {trend_icon} {trend.title()}")
                st.write(a.get("summary") or "")
                st.markdown("---")

    # ── Notes ─────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Notes**")

    note_counter_key = f"note_counter_{account_id}"
    if note_counter_key not in st.session_state:
        st.session_state[note_counter_key] = 0
    note_text = st.text_area("Add a note",
                              placeholder="Type a note about this account...",
                              key=f"note_input_{account_id}_{st.session_state[note_counter_key]}")
    if st.button("Save note", key=f"save_note_{account_id}"):
        if note_text.strip():
            db.save_note(account_id, note_text)
            st.session_state[note_counter_key] += 1
            st.rerun()

    notes = db.get_notes(account_id)
    if notes:
        for n in notes:
            ts = (n.get("created_at") or "")[:16].replace("T", " ")
            st.markdown(f"<small style='color:#667085'>{ts}</small>", unsafe_allow_html=True)
            st.write(n.get("note_text") or "")
            st.markdown("---")

    # ── NetSuite Resources (fetch once per session, cached) ───────────────────
    resources_key = f"resources_{account_id}"
    if resources_key not in st.session_state:
        recent_sigs = db.get_signals_for_account(account_id, days=7)
        sig_summaries = " | ".join(s.get("summary", "") for s in recent_sigs[:5]) or ""
        st.session_state[resources_key] = content_utils.get_relevant_resources(
            account_name=acct.get("company_name", ""),
            industry=acct.get("industry", ""),
            tech_stack=acct.get("tech_stack"),
            signal_summaries=sig_summaries,
        )

    # ── Content Generation ────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Content Generation**")

    cg_cols = st.columns(2)

    with cg_cols[0]:
        if st.button("Send SDR Briefing", key=f"gen_briefing_{account_id}", use_container_width=True, type="primary"):
            st.session_state[f"show_briefing_{account_id}"] = True

    with cg_cols[1]:
        _op_ready = bool(st.session_state.get(f"onepager_url_{account_id}") or acct.get("one_pager_url"))
        _op_label = "✅ One Pager Ready" if _op_ready else "Generate One Pager"
        if st.button(_op_label, key=f"gen_onepager_{account_id}", use_container_width=True):
            st.session_state[f"show_onepager_{account_id}"] = True

    # ── Similar Customers ─────────────────────────────────────────────────────
    locked_customers = db.get_locked_customers(account_id)
    locked_count = len(locked_customers)
    sc_header = f"Similar Customers ({locked_count} locked)" if locked_count else "Similar Customers"

    with st.expander(sc_header, expanded=False):
        # Locked subsection
        if locked_customers:
            st.markdown("**Locked**")
            for c in locked_customers:
                c_id = str(c["id"])
                cw = c.get("website") or ""
                url = cw if cw.startswith("http") else f"https://{cw}" if cw else None
                name_md = f"[{c['company_name']}]({url})" if url else c["company_name"]
                lk_cols = st.columns([4, 1])
                with lk_cols[0]:
                    st.markdown(name_md)
                    if c.get("industry"):
                        st.caption(c["industry"])
                with lk_cols[1]:
                    if st.button("Dismiss", key=f"dismiss_locked_{account_id}_{c_id}"):
                        db.dismiss_customer(account_id, c_id)
                        st.rerun()
            st.divider()

        # Find button
        sc_results_key = f"sc_results_{account_id}"
        if st.button("Find Similar Customers", key=f"find_sc_{account_id}"):
            dismissed_ids = db.get_dismissed_customer_ids(account_id)
            locked_ids = [str(c["id"]) for c in locked_customers]
            excluded = dismissed_ids + locked_ids
            with st.spinner("Finding similar customers..."):
                try:
                    st.session_state[sc_results_key] = db.get_similar_customers_naics(
                        account_id, limit=10, excluded_ids=excluded
                    )
                except Exception as e:
                    st.error(f"Lookup failed: {e}")
                    st.session_state[sc_results_key] = []

        # ── Manual keyword search (searches all customers) ────────────────────
        sc_search_key = f"sc_search_{account_id}"
        sc_search_results_key = f"sc_search_results_{account_id}"
        sc_cols = st.columns([5, 1])
        with sc_cols[0]:
            sc_search = st.text_input("Search all customers...", key=sc_search_key,
                                      label_visibility="collapsed",
                                      placeholder="Search all customers by name, industry, what they do...")
        with sc_cols[1]:
            search_clicked = st.button("Search", key=f"sc_search_btn_{account_id}", use_container_width=True)

        if search_clicked and sc_search.strip():
            dismissed_ids = db.get_dismissed_customer_ids(account_id)
            locked_ids = [str(c["id"]) for c in locked_customers]
            excluded = dismissed_ids + locked_ids
            st.session_state[sc_search_results_key] = db.search_customers(
                sc_search.strip(), excluded_ids=excluded, limit=20
            )

        search_results = st.session_state.get(sc_search_results_key, [])
        if search_results:
            st.markdown("**Search Results**")
            for c in search_results:
                c_id = str(c["id"])
                cw = c.get("website") or ""
                url = cw if cw.startswith("http") else f"https://{cw}" if cw else None
                name_md = f"[{c['company_name']}]({url})" if url else c["company_name"]
                r_cols = st.columns([4, 1, 1])
                with r_cols[0]:
                    st.markdown(name_md)
                    caption_parts = [p for p in [c.get("industry"), c.get("what_they_do")] if p]
                    if caption_parts:
                        st.caption(" · ".join(caption_parts[:2]))
                with r_cols[1]:
                    if st.button("Lock", key=f"lock_srch_{account_id}_{c_id}"):
                        db.lock_customer(account_id, c_id)
                        st.session_state[sc_search_results_key] = [
                            x for x in st.session_state[sc_search_results_key] if str(x["id"]) != c_id
                        ]
                        st.rerun()
                with r_cols[2]:
                    if st.button("Dismiss", key=f"dismiss_srch_{account_id}_{c_id}"):
                        db.dismiss_customer(account_id, c_id)
                        st.session_state[sc_search_results_key] = [
                            x for x in st.session_state[sc_search_results_key] if str(x["id"]) != c_id
                        ]
                        st.rerun()
        elif search_clicked and sc_search.strip():
            st.caption("No customers found for that search.")

        # ── AI match results ───────────────────────────────────────────────────
        results = st.session_state.get(sc_results_key, [])
        if results:
            st.markdown("**AI Match Results**")
            for c in results:
                c_id = str(c["id"])
                cw = c.get("website") or ""
                url = cw if cw.startswith("http") else f"https://{cw}" if cw else None
                name_md = f"[{c['company_name']}]({url})" if url else c["company_name"]
                r_cols = st.columns([4, 1, 1])
                with r_cols[0]:
                    st.markdown(name_md)
                    if c.get("reason"):
                        st.caption(c["reason"])
                    elif c.get("industry"):
                        st.caption(c["industry"])
                with r_cols[1]:
                    if st.button("Lock", key=f"lock_sc_{account_id}_{c_id}"):
                        db.lock_customer(account_id, c_id)
                        st.session_state[sc_results_key] = [
                            x for x in st.session_state[sc_results_key] if str(x["id"]) != c_id
                        ]
                        st.rerun()
                with r_cols[2]:
                    if st.button("Dismiss", key=f"dismiss_sc_{account_id}_{c_id}"):
                        db.dismiss_customer(account_id, c_id)
                        st.session_state[sc_results_key] = [
                            x for x in st.session_state[sc_results_key] if str(x["id"]) != c_id
                        ]
                        st.rerun()

    # ── Outreach ──────────────────────────────────────────────────────────────
    with st.expander("Outreach", expanded=False):
        with st.expander("Edit Prompt Template", expanded=False):
            st.caption("This template applies to all outreach generation across all accounts.")
            current_template = db.get_outreach_prompt(REP_ID)
            tmpl_text = st.text_area("Prompt template", value=current_template, height=400,
                                     key=f"outreach_tmpl_{account_id}", label_visibility="collapsed")
            tmpl_cols = st.columns(2)
            with tmpl_cols[0]:
                if st.button("Save Template", key=f"save_tmpl_{account_id}"):
                    db.save_outreach_prompt(REP_ID, tmpl_text)
                    st.success("Prompt saved.")
            with tmpl_cols[1]:
                if st.button("Reset to Default", key=f"reset_tmpl_{account_id}"):
                    db.save_outreach_prompt(REP_ID, db._OUTREACH_DEFAULT)
                    st.success("Reset to default.")
                    st.rerun()

        mention = st.text_input("Mention something specific (optional)",
                                placeholder="e.g. their recent warehouse expansion",
                                key=f"outreach_mention_{account_id}")

        outreach_key = f"outreach_result_{account_id}"
        stored_outreach = db.get_outreach(account_id) if hasattr(db, "get_outreach") else None

        if st.button("Generate Outreach", key=f"gen_outreach_{account_id}", type="primary"):
            if not mention and stored_outreach:
                st.session_state[outreach_key] = stored_outreach
            else:
                with st.spinner("Generating outreach..."):
                    try:
                        _recent = db.get_signals_for_account(account_id, days=60)
                        _sig_summaries = " | ".join(
                            s.get("summary", "") for s in _recent[:5]
                        ) or "No recent signals."
                        _ts = acct.get("tech_stack") or []
                        _template = db.get_outreach_prompt(REP_ID)

                        _ctx = {
                            "account_name": acct.get("company_name", ""),
                            "industry": acct.get("industry") or "unknown",
                            "naics_description": acct.get("naics_description") or "",
                            "naics_notes": acct.get("naics_notes") or "",
                            "tech_stack": ", ".join(_ts) if _ts else "unknown",
                            "signal_summaries": _sig_summaries,
                        }
                        _prompt = _template.format(**_ctx)
                        if mention:
                            _prompt += (
                                f"\n\nThe rep wants to specifically mention: {mention}\n\n"
                                "Build the outreach around this specific point, incorporating it naturally "
                                "with the signal and hook. When a specific mention is provided, you may "
                                "use up to 4 sentences plus a CTA instead of the standard 2 sentences."
                            )
                        _cl_out = _anthropic.Anthropic(api_key=_get_anthropic_key())
                        _resp_out = _cl_out.messages.create(
                            model=MODEL, max_tokens=512,
                            messages=[{"role": "user", "content": _prompt}]
                        )
                        _result = _resp_out.content[0].text.strip()
                        db.log_ai_call({
                            "rep_id": REP_ID, "call_type": "outreach_generate",
                            "prompt_used": _prompt, "model_version": MODEL,
                            "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        })
                        st.session_state[outreach_key] = _result
                    except Exception as _e:
                        st.error(f"Generation failed: {_e}")

        if st.session_state.get(outreach_key):
            st.text_area("Outreach", value=st.session_state[outreach_key], height=200,
                         key=f"outreach_display_{account_id}", label_visibility="collapsed")

    # ── Generate Briefing ─────────────────────────────────────────────────────
    briefing_sent_key = f"briefing_sent_{account_id}"
    if st.session_state.get(f"show_briefing_{account_id}"):
        st.markdown("---")
        st.markdown("**Briefing**")
        if st.session_state.get(briefing_sent_key):
            st.success(st.session_state[briefing_sent_key])
        else:
            with st.spinner("Assembling briefing..."):
                # ── Fetch data ────────────────────────────────────────────────
                signals       = db.get_signals_for_account(account_id, days=365)
                events_list   = db.get_flagged_events(account_id)
                notes_list    = db.get_notes(account_id)
                company       = acct.get("company_name", "Unknown")
                sdr_name      = acct.get("sdr_name") or "there"
                domain        = acct.get("domain") or ""
                ns_url        = acct.get("nscorp_url") or ""
                today_str     = datetime.date.today().strftime("%B %-d, %Y")

                # ── Lead highlight — auto-generate if missing ─────────────────
                lead_highlight = (
                    st.session_state.get(f"lead_highlight_{account_id}")
                    or db.get_lead_highlight(account_id)
                )
                if not lead_highlight:
                    _sig_text = "\n".join(
                        f"[{s.get('signal_type','')}] {s.get('headline','')} — {s.get('summary','')}"
                        for s in signals[:10]
                    ) or "No signals available."
                    _lh_prompt = (
                        "You are a NetSuite sales rep writing a personal note to your SDR about why they should work this account.\n\n"
                        "Write 2-3 short sentences in first person, as if Brian is talking directly to the SDR. "
                        "Be specific about what makes this account worth pursuing right now. "
                        "Reference signals if available. Sound like a rep who is genuinely excited about the opportunity, not a marketer.\n\n"
                        "Rules:\n"
                        "- First person, conversational — \"I've been watching these guys\" not \"this company presents an opportunity\"\n"
                        "- No marketing language, no ICP references, no em dashes\n"
                        "- Short sentences only\n"
                        "- Specific beats generic — mention what you actually see, not what could theoretically be true\n\n"
                        f"Company: {company}\n"
                        f"Industry: {acct.get('industry') or 'unknown'}\n"
                        f"NAICS: {acct.get('naics_description') or ''}\n"
                        f"What they do: {acct.get('naics_notes') or ''}\n"
                        f"Signals:\n{_sig_text}"
                    )
                    try:
                        _cl = _anthropic.Anthropic(api_key=_get_anthropic_key())
                        _r = _cl.messages.create(model=MODEL, max_tokens=256,
                                                 messages=[{"role": "user", "content": _lh_prompt}])
                        lead_highlight = _r.content[0].text.strip()
                        db.save_lead_highlight(account_id, lead_highlight)
                        st.session_state[f"lead_highlight_{account_id}"] = lead_highlight
                        db.log_ai_call({"rep_id": REP_ID, "call_type": "lead_highlight_auto",
                                        "prompt_used": _lh_prompt, "model_version": MODEL,
                                        "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
                    except Exception:
                        lead_highlight = ""

                # ── Battle card — ensure HTML is in session for attachment ────
                one_pager_url = (
                    st.session_state.get(f"onepager_url_{account_id}")
                    or acct.get("one_pager_url")
                )
                op_html_attach = st.session_state.get(f"onepager_html_{account_id}")
                if not op_html_attach:
                    try:
                        with st.spinner("Generating battle card..."):
                            import one_pager as _op_mod
                            op_html_attach = _op_mod.generate_one_pager(acct, signals, notes_list)
                            st.session_state[f"onepager_html_{account_id}"] = op_html_attach
                            if not one_pager_url:
                                one_pager_url = db.upload_one_pager(account_id, op_html_attach, company)
                                st.session_state[f"onepager_url_{account_id}"] = one_pager_url
                                db.log_ai_call({"rep_id": REP_ID, "call_type": "one_pager_auto",
                                                "prompt_used": f"one_pager:{account_id}", "model_version": MODEL,
                                                "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
                    except Exception:
                        op_html_attach = None

                # ── Contacts for briefing ─────────────────────────────────────
                briefing_contacts = db.get_contacts_for_account(account_id)

                # ── Resources ─────────────────────────────────────────────────
                briefing_resources = st.session_state.get(resources_key) or []
                if not briefing_resources:
                    briefing_resources = content_utils.get_relevant_resources(
                        company, acct.get("industry", ""), acct.get("tech_stack"), ""
                    )

                # ── Similar customers — locked first, fall back to NAICS ──────
                _briefing_locked = db.get_locked_customers(account_id)
                _briefing_sc_label = "Similar Customers"
                if _briefing_locked:
                    similar_list = _briefing_locked
                else:
                    # Silent fallback: top 3 NAICS matches
                    _briefing_sc_label = "Possible Similar Customers"
                    try:
                        dismissed_ids = db.get_dismissed_customer_ids(account_id)
                        similar_list = db.get_similar_customers_naics(
                            account_id, limit=3, excluded_ids=dismissed_ids
                        )
                    except Exception:
                        similar_list = []

                # ── HTML helpers ──────────────────────────────────────────────
                HR  = '<hr style="border:none;border-top:1px solid #f0f0f0;margin:16px 0;">'
                LNK = '<a href="{url}" style="color:#36677D;text-decoration:none;">{text}</a>'
                SEC = '<p style="margin:0 0 6px 0;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">{label}</p>'

                def lnk(url, text):
                    if not url:
                        return text
                    u = str(url).strip()
                    if not u.startswith("http"):
                        u = f"https://{u}"
                    u = u.replace('"', "%22").replace("'", "%27").replace("<", "%3C").replace(">", "%3E")
                    return f'<a href="{u}" style="color:#36677D;text-decoration:none;">{text}</a>'

                def sec(label):
                    return f'<p style="margin:0 0 6px 0;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">{label}</p>'

                parts = []

                # 1. Intro
                _intro_greeting = f"Hey {sdr_name}," if sdr_name and sdr_name != "Hey there," else "Hey,"
                parts.append(f'<p style="margin:0 0 16px 0;">{_intro_greeting} I\'m excited to work this lead with you. Here\'s what I\'ve pulled together to get you up to speed:</p>')

                # 2. WHY THIS ACCOUNT (always)
                parts.append(HR)
                parts.append(sec("Why This Account"))
                parts.append(f'<p style="margin:0 0 16px 0;">{lead_highlight}</p>')

                # 3. WHO TO CALL (conditional)
                if briefing_contacts:
                    parts.append(HR)
                    parts.append(sec("Who to Call"))
                    wtc_lines = []
                    for _bc in briefing_contacts:
                        cell_star = " ★" if _bc.get("cell_confirmed") else ""
                        _bc_parts = [p for p in [_bc.get("name"), _bc.get("title")] if p]
                        _bc_contact = [p for p in [_bc.get("email"), (_bc.get("phone") or "") + cell_star if _bc.get("phone") else None] if p]
                        line = " · ".join(_bc_parts)
                        if _bc_contact:
                            line += " &nbsp;— " + " · ".join(_bc_contact)
                        if _bc.get("linkedin_url"):
                            line += f" &nbsp;{lnk(_bc['linkedin_url'], 'LinkedIn')}"
                        wtc_lines.append(line)
                    parts.append("<p style=\"margin:0 0 16px 0;\">" + "<br>".join(wtc_lines) + "</p>")

                # 4. WHY NETSUITE (conditional — only if generated)
                _industry_brief = st.session_state.get(f"industry_brief_{account_id}")
                if _industry_brief:
                    parts.append(HR)
                    parts.append(sec("Why NetSuite"))
                    brief_html = _industry_brief.replace("\n", "<br>").replace("<br>- ", "<br>• ")
                    parts.append(f'<p style="margin:0 0 16px 0;">{brief_html}</p>')

                # 5. ACCOUNT
                parts.append(HR)
                parts.append(sec("Account"))
                acct_lines = [f'<strong>{company}</strong>']
                links = []
                if ns_url:
                    links.append(lnk(ns_url, "NS Record"))
                if domain:
                    links.append(lnk(f"https://{domain}", "Website"))
                _zi_id = acct.get("zi_id") or ""
                if links:
                    acct_lines.append(" &nbsp;|&nbsp; ".join(links))
                parts.append("<p style=\"margin:0 0 16px 0;\">" + "<br>".join(acct_lines) + "</p>")

                # 6. NOTES (up to 3, conditional)
                if notes_list:
                    parts.append(HR)
                    parts.append(sec("Notes"))
                    note_lines = []
                    for n in notes_list[:3]:
                        raw_date = (n.get("created_at") or "")[:10]
                        fmt_date = raw_date[5:].replace("-", "/") if len(raw_date) >= 10 else raw_date
                        txt = (n.get("note_text") or "").replace("<", "&lt;").replace(">", "&gt;")
                        note_lines.append(f'<span style="color:#888;">{fmt_date}</span> — {txt}')
                    parts.append("<p style=\"margin:0 0 16px 0;\">" + "<br>".join(note_lines) + "</p>")

                # 5. BATTLE CARD (conditional — attached as .htm)
                if op_html_attach:
                    parts.append(HR)
                    parts.append(sec("Battle Card"))
                    parts.append('<p style="margin:0 0 16px 0;">See attached battle card.</p>')

                # 6. SIGNALS (up to 5, conditional)
                if signals:
                    parts.append(HR)
                    parts.append(sec("Signals"))
                    sig_html = []
                    for s in signals[:5]:
                        hl  = (s.get("headline") or "").replace("<","&lt;").replace(">","&gt;")
                        sm  = (s.get("summary") or "").replace("<","&lt;").replace(">","&gt;")
                        st_ = (s.get("signal_type") or "other").replace("_"," ")
                        furl = s.get("file_url")
                        view = f' &nbsp;{lnk(furl, "View")}' if furl else ""
                        sig_html.append(
                            f'<strong>{hl}</strong><br>{sm}<br>'
                            f'<span style="color:#888;font-size:12px;">{st_}</span>{view}'
                        )
                    parts.append("<p style=\"margin:0 0 16px 0;\">" + "<br><br>".join(sig_html) + "</p>")

                # 7. SIMILAR CUSTOMERS (conditional)
                if similar_list:
                    parts.append(HR)
                    parts.append(sec(_briefing_sc_label))
                    sc_html = []
                    for c in similar_list:
                        cw = c.get("website") or ""
                        cn = (c.get("company_name") or "").replace("<","&lt;").replace(">","&gt;")
                        sc_html.append(lnk(cw, cn) if cw else cn)
                    parts.append("<p style=\"margin:0 0 16px 0;\">" + "<br>".join(sc_html) + "</p>")

                # 8. EVENTS (up to 2 flagged, conditional)
                if events_list:
                    parts.append(HR)
                    parts.append(sec("Events"))
                    ev_html = []
                    for e in events_list[:2]:
                        raw_date = (e.get("event_date") or "")
                        fmt_date = raw_date[5:].replace("-", "/") if len(raw_date) >= 10 else raw_date
                        ename = (e.get("event_name") or "").replace("<","&lt;").replace(">","&gt;")
                        ev_links = []
                        if e.get("registration_url"):
                            ev_links.append(lnk(e["registration_url"], "Register"))
                        if e.get("seismic_url"):
                            ev_links.append(lnk(e["seismic_url"], "Seismic"))
                        link_str = " &nbsp;" + " &nbsp;".join(ev_links) if ev_links else ""
                        ev_html.append(f'<strong>{fmt_date}</strong> — {ename}{link_str}')
                    parts.append("<p style=\"margin:0 0 16px 0;\">" + "<br>".join(ev_html) + "</p>")

                # 9. NETSUITE RESOURCES (conditional)
                if briefing_resources:
                    parts.append(HR)
                    parts.append(sec("NetSuite Resources"))
                    res_html = [lnk(r["url"], r["title"]) for r in briefing_resources]
                    parts.append("<p style=\"margin:0 0 16px 0;\">" + "<br>".join(res_html) + "</p>")

                body_inner = "\n".join(parts)
                body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#ffffff;">
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:32px 24px;color:#222;font-size:14px;line-height:1.5;">
{body_inner}
<hr style="border:none;border-top:1px solid #f0f0f0;margin:16px 0;">
<p style="margin:0;font-size:11px;color:#aaa;">Generated by TAL Command Center · {today_str}</p>
</div>
</body></html>"""

                try:
                    import base64
                    import json as _json
                    from email.mime.text import MIMEText
                    from email.mime.multipart import MIMEMultipart
                    from email.mime.base import MIMEBase
                    from email import encoders as _encoders
                    from google.oauth2.credentials import Credentials
                    from googleapiclient.discovery import build

                    try:
                        creds = Credentials.from_authorized_user_info(dict(st.secrets["gmail_token"]))
                    except Exception as _cred_err:
                        token_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gmail_token.json")
                        if not os.path.exists(token_path):
                            raise RuntimeError(f"gmail_token secret failed ({_cred_err}) and no local token file found") from _cred_err
                        creds = Credentials.from_authorized_user_info(_json.load(open(token_path)))
                    service = build("gmail", "v1", credentials=creds)

                    if op_html_attach:
                        msg = MIMEMultipart("mixed")
                        msg["to"] = "brian.br.oneill@oracle.com"
                        msg["subject"] = f"TCC Briefing: {company}"
                        msg.attach(MIMEText(body, "html"))
                        safe_attach = (company or "account").replace(" ", "_").replace("/", "-")
                        att = MIMEBase("text", "html")
                        att.set_payload(op_html_attach.encode("utf-8"))
                        _encoders.encode_base64(att)
                        att.add_header("Content-Disposition", "attachment", filename=f"{safe_attach}_battle_card.htm")
                        msg.attach(att)
                    else:
                        msg = MIMEText(body, "html")
                        msg["to"] = "brian.br.oneill@oracle.com"
                        msg["subject"] = f"TCC Briefing: {company}"
                    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                    service.users().messages().send(userId="me", body={"raw": raw}).execute()
                    db.mark_briefing_sent(account_id)
                    success_msg = "Briefing sent to brian.br.oneill@oracle.com"
                    st.session_state[briefing_sent_key] = success_msg
                    st.success(success_msg)
                except Exception as e:
                    st.error(f"Email send failed: {e}")

    # ── Generate One Pager ────────────────────────────────────────────────────
    if st.session_state.get(f"show_onepager_{account_id}"):
        st.markdown("---")
        st.markdown("**One Pager**")

        op_key = f"onepager_html_{account_id}"
        if not st.session_state.get(op_key):
            with st.spinner("Generating one pager with Claude..."):
                import one_pager as _op
                signals = db.get_signals_for_account(account_id, days=365)
                notes = db.get_notes(account_id)
                try:
                    html = _op.generate_one_pager(acct, signals, notes)
                    st.session_state[op_key] = html
                    db.log_ai_call({
                        "rep_id": REP_ID,
                        "call_type": "one_pager_generation",
                        "prompt_used": f"one_pager:{account_id}",
                        "model_version": MODEL,
                        "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })
                except Exception as e:
                    st.error(f"One pager generation failed: {e}")

        if st.session_state.get(op_key):
            # Upload to Supabase Storage and store URL
            url_key = f"onepager_url_{account_id}"
            if url_key not in st.session_state:
                with st.spinner("Saving one pager..."):
                    try:
                        op_url = db.upload_one_pager(
                            account_id,
                            st.session_state[op_key],
                            acct.get("company_name") or "account",
                        )
                        st.session_state[url_key] = op_url
                    except Exception as _ue:
                        st.warning(f"Upload failed: {_ue}")
            op_url = st.session_state.get(url_key) or acct.get("one_pager_url")
            if op_url:
                st.success("One pager saved.")
            safe_name = (acct.get("company_name") or "account").replace(" ", "_").replace("/", "-")
            st.download_button(
                label="Download One Pager (HTML)",
                data=st.session_state[op_key].encode("utf-8"),
                file_name=f"{safe_name}_one_pager.html",
                mime="text/html",
                key=f"dl_onepager_{account_id}",
            )
            if st.button("Regenerate", key=f"regen_onepager_{account_id}"):
                del st.session_state[op_key]
                if f"onepager_url_{account_id}" in st.session_state:
                    del st.session_state[f"onepager_url_{account_id}"]
                st.rerun()

    # ── Relevant Events ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Upcoming Events**")
    acct_events = db.get_events_for_account(account_id)
    if not acct_events:
        st.caption("No upcoming events matched to this account.")
    else:
        for e in acct_events:
            event_id = e.get("id") or e.get("event_id")
            reg = f"[Register]({e['registration_url']})" if e.get("registration_url") else ""
            seismic = f"[Seismic]({e['seismic_url']})" if e.get("seismic_url") else ""
            links = "  ·  ".join(filter(None, [reg, seismic]))
            etype = (e.get("event_type") or "").replace("_", " ").title()
            region = f" · {e['region']}" if e.get("region") else ""
            st.markdown(f"**{e.get('event_date', '')}** — {e.get('event_name', '')}  \n"
                        f"<small style='color:#667085'>{etype}{region}</small>  {links}",
                        unsafe_allow_html=True)

            is_flagged = e.get("flagged_for_briefing", False)

            ev_btn1, ev_btn2 = st.columns(2)
            with ev_btn1:
                flag_label = "🚩 Flagged for Briefing" if is_flagged else "Flag for Briefing"
                if st.button(flag_label, key=f"flag_{account_id}_{event_id}"):
                    db.flag_event_for_briefing(account_id, event_id, not is_flagged)
                    st.rerun()
            with ev_btn2:
                if st.button("Generate Invite", key=f"invite_{account_id}_{event_id}"):
                    st.session_state[f"gen_invite_{account_id}_{event_id}"] = True

            if st.session_state.get(f"gen_invite_{account_id}_{event_id}"):
                existing_invite = db.get_event_invite(account_id, event_id)
                if existing_invite and not st.session_state.get(f"reinvite_{account_id}_{event_id}"):
                    invite_text = existing_invite["invite_body"]
                else:
                    with st.spinner("Generating invite..."):
                        ts_list = acct.get("tech_stack") or []
                        recent_sigs = db.get_signals_for_account(account_id, days=30)
                        sig_summaries = " | ".join(s.get("summary", "") for s in recent_sigs[:3]) or "No recent signals."
                        notes_list = db.get_notes(account_id)
                        notes_text = " | ".join(n.get("note_text", "") for n in notes_list[:3]) or "No notes."
                        invite_prompt = (
                            "You are Brian O'Neill, a NetSuite ERP sales rep inviting a prospect to an event.\n\n"
                            f"Account: {acct.get('company_name', '')}\n"
                            f"Industry: {acct.get('industry') or 'unknown'}\n"
                            f"Tech stack: {', '.join(ts_list) or 'Unknown'}\n"
                            f"Recent signals: {sig_summaries}\n"
                            f"Notes: {notes_text}\n\n"
                            f"Event: {e.get('event_name', '')}\n"
                            f"Event date: {e.get('event_date', '')}\n"
                            f"Event type: {etype}\n"
                            f"Registration link: {e.get('registration_url') or 'N/A'}\n\n"
                        ) + _OUTREACH_TONE.replace(
                            "2. Signal or trigger reference: one sentence. Why you are reaching out right now.",
                            "2. Event reference: one sentence. Why this event is relevant to them right now. Include the registration link."
                        ) + (
                            "\n\nBefore the email body, write a subject line on its own line in this format:\n"
                            "Subject: [subject here]\n\n"
                            "Subject line rules: short, lowercase is fine, sounds like a human typed it fast. "
                            "No colons, no buzzwords, nothing polished. Examples: 'quick one', 'saw this and thought of you', 're: the AI event next month'."
                        )
                        _cl2 = _anthropic.Anthropic(api_key=_get_anthropic_key())
                        resp2 = _cl2.messages.create(model=MODEL, max_tokens=512,
                                                     messages=[{"role": "user", "content": invite_prompt}])
                        invite_text = resp2.content[0].text.strip()
                        db.insert_event_invite({
                            "account_id": account_id, "event_id": event_id,
                            "invite_body": invite_text, "model_version": MODEL,
                            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        })
                        db.log_ai_call({"rep_id": REP_ID, "call_type": "event_invite",
                                        "prompt_used": invite_prompt, "model_version": MODEL,
                                        "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
                        st.session_state[f"reinvite_{account_id}_{event_id}"] = False
                st.text_area("Invite", value=invite_text, height=150,
                             key=f"invite_display_{account_id}_{event_id}", label_visibility="collapsed")
                if st.button("Regenerate Invite", key=f"reinvite_btn_{account_id}_{event_id}"):
                    st.session_state[f"reinvite_{account_id}_{event_id}"] = True
                    st.rerun()

    # ── NetSuite Resources ────────────────────────────────────────────────────
    resources = st.session_state.get(resources_key, [])
    if resources:
        st.divider()
        st.markdown("**NetSuite Resources**")
        for r in resources:
            st.markdown(f"- [{r['title']}]({r['url']})")
            st.write("")
