"""Account detail page."""
import os
import datetime
import streamlit as st
import anthropic as _anthropic

import db
from db import get_account
from config import get_anthropic_key as _get_anthropic_key, MODEL, REP_ID
from pages._shared import go, back_btn

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
    back_btn("← Back to TAL", "tal")

    account_id = st.session_state.get("selected_account")
    if not account_id:
        st.warning("No account selected.")
        return

    acct = get_account(account_id)
    if not acct:
        st.error(f"Account {account_id} not found.")
        return

    st.markdown(f"## {acct.get('company_name', 'Unknown')}")

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

    # ── Weekly Analysis ───────────────────────────────────────────────────────
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

    # ── Outreach Suggestions ──────────────────────────────────────────────────
    with st.expander("Outreach Suggestions"):
        outreach_resp = (
            db.get_client()
            .table("outreach_templates")
            .select("trigger_type, email_body, generated_at")
            .eq("account_id", account_id)
            .order("generated_at", desc=True)
            .limit(5)
            .execute()
        )
        suggestions = outreach_resp.data or []
        if not suggestions:
            st.caption("No outreach suggestions generated yet.")
        else:
            for o in suggestions:
                st.markdown(f"**{(o.get('trigger_type') or 'signal').replace('_', ' ').title()}** · {(o.get('generated_at') or '')[:10]}")
                st.text_area("Email", value=o.get("email_body") or "", height=150, disabled=True,
                             key=f"outreach_{hash(str(o))}", label_visibility="collapsed")

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

            ae_resp = db.get_client().table("account_events").select("flagged_for_briefing").eq("account_id", account_id).eq("event_id", event_id).limit(1).execute()
            is_flagged = (ae_resp.data or [{}])[0].get("flagged_for_briefing", False)

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
            st.write("")

    # ── Content Generation ────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Content Generation**")

    cg_cols = st.columns(2)

    with cg_cols[0]:
        if st.button("Generate Outreach", key=f"gen_outreach_{account_id}", use_container_width=True):
            st.session_state[f"show_outreach_{account_id}"] = True

    with cg_cols[1]:
        if st.button("Generate Briefing", key=f"gen_briefing_{account_id}", use_container_width=True):
            st.session_state[f"show_briefing_{account_id}"] = True

    # ── Generate Outreach ─────────────────────────────────────────────────────
    if st.session_state.get(f"show_outreach_{account_id}"):
        st.markdown("---")
        st.markdown("**Outreach Draft**")

        existing_outreach_resp = (
            db.get_client().table("outreach_templates")
            .select("email_body, trigger_type, generated_at")
            .eq("account_id", account_id)
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )
        existing = (existing_outreach_resp.data or [{}])[0]

        regen_key = f"regen_outreach_{account_id}"
        force_regen = st.session_state.get(regen_key, False)

        if existing.get("email_body") and not force_regen:
            email_draft = existing["email_body"]
            st.caption(f"From pipeline · {(existing.get('generated_at') or '')[:10]}")
        else:
            with st.spinner("Generating outreach with Claude..."):
                context = db.get_account_full_context(account_id)
                acct_info = context["account"]
                signals = context["signals"]
                signal_summary = signals[0]["summary"] if signals else "No recent signals."
                signal_type = signals[0].get("signal_type", "other") if signals else "other"
                outreach_prompt = (
                    "You are Brian O'Neill, a NetSuite ERP sales rep. "
                    "Write a short prospecting email to a decision-maker at the company below.\n\n"
                    f"Signal type: {signal_type}\n"
                    f"Prospect company: {acct_info.get('company_name', '')}\n"
                    f"Industry: {acct_info.get('industry') or 'unknown'}\n"
                    f"Signal summary: {signal_summary}\n\n"
                ) + _OUTREACH_TONE
                _cl = _anthropic.Anthropic(api_key=_get_anthropic_key())
                resp = _cl.messages.create(model=MODEL, max_tokens=512,
                                           messages=[{"role": "user", "content": outreach_prompt}])
                email_draft = resp.content[0].text.strip()
                db.insert_outreach_suggestion({
                    "rep_id": REP_ID,
                    "account_id": account_id,
                    "trigger_type": signal_type,
                    "email_body": email_draft,
                    "model_version": MODEL,
                    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
                db.log_ai_call({
                    "rep_id": REP_ID,
                    "call_type": "outreach_generation",
                    "prompt_used": outreach_prompt,
                    "model_version": MODEL,
                    "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
                st.session_state[regen_key] = False

        st.text_area("Outreach email", value=email_draft, height=200,
                     key=f"outreach_display_{account_id}", label_visibility="collapsed")
        if st.button("Regenerate", key=f"regen_btn_{account_id}"):
            st.session_state[regen_key] = True
            st.rerun()

    # ── Generate Briefing ─────────────────────────────────────────────────────
    if st.session_state.get(f"show_briefing_{account_id}"):
        st.markdown("---")
        st.markdown("**Briefing**")
        with st.spinner("Assembling briefing and sending email..."):
            context = db.get_account_full_context(account_id)
            acct_info = context["account"]
            signals = context["signals"]
            events_list = db.get_flagged_events(account_id)
            outreach = context["outreach"]
            notes_list = context["notes"]

            if outreach.get("email_body"):
                outreach_text = outreach["email_body"]
            else:
                _cl = _anthropic.Anthropic(api_key=_get_anthropic_key())
                sig_sum = signals[0]["summary"] if signals else "No recent signals."
                sig_type = signals[0].get("signal_type", "other") if signals else "other"
                p = (
                    "You are Brian O'Neill, a NetSuite ERP sales rep. "
                    "Write a short prospecting email to a decision-maker at the company below.\n\n"
                    f"Prospect company: {acct_info.get('company_name', '')}\n"
                    f"Industry: {acct_info.get('industry') or 'unknown'}\n"
                    f"Signal summary: {sig_sum}\n\n"
                ) + _OUTREACH_TONE
                r = _cl.messages.create(model=MODEL, max_tokens=512,
                                        messages=[{"role": "user", "content": p}])
                outreach_text = r.content[0].text.strip()
                db.insert_outreach_suggestion({
                    "rep_id": REP_ID, "account_id": account_id,
                    "trigger_type": sig_type, "email_body": outreach_text,
                    "model_version": MODEL,
                    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })

            today_str = datetime.date.today().strftime("%B %-d, %Y")
            company = acct_info.get("company_name", "Unknown")

            signals_block = "\n".join(
                f"- [{s.get('signal_date','')[:10]}] {s.get('signal_type','').upper()}: {s.get('summary','')}"
                for s in signals
            ) or "No signals in last 30 days."

            events_block = "\n".join(
                f"- {e.get('event_date','')} | {e.get('event_name','')} | {e.get('registration_url') or 'No link'}"
                + (f"\n  Seismic: {e['seismic_url']}" if e.get("seismic_url") else "")
                + (f"\n  Invite: {e['invite_body']}" if e.get("invite_body") else "")
                for e in events_list
            ) or "No flagged events."

            notes_block = "\n".join(
                f"- {(n.get('created_at',''))[:10]}: {n.get('note_text','')}"
                for n in notes_list
            ) or "No notes."

            ns_url = acct_info.get("nscorp_url") or ""
            ns_line = f"NetSuite: {ns_url}" if ns_url else ""

            body = f"""TCC Account Briefing
Account: {company}
Date: {today_str}
{ns_line}

--- SIGNALS ---
{signals_block}

--- UPCOMING EVENTS ---
{events_block}

--- OUTREACH DRAFT ---
{outreach_text}

--- NOTES ---
{notes_block}
"""
            try:
                import base64
                import json as _json
                from email.mime.text import MIMEText
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                token_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gmail_token.json")
                creds = Credentials.from_authorized_user_info(_json.load(open(token_path)))
                service = build("gmail", "v1", credentials=creds)

                msg = MIMEText(body)
                msg["to"] = "brian.br.oneill@oracle.com"
                msg["subject"] = f"TCC Briefing: {company} - {today_str}"
                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                service.users().messages().send(userId="me", body={"raw": raw}).execute()
                db.mark_briefing_sent(account_id)
                st.success(f"Briefing sent to brian.br.oneill@oracle.com")
            except Exception as e:
                st.error(f"Email send failed: {e}")
                st.text_area("Briefing (copy manually)", value=body, height=300,
                             key=f"briefing_fallback_{account_id}", label_visibility="collapsed")
