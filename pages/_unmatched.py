"""Unmatched signals review page."""
import datetime
import streamlit as st

import db
from pages._shared import back_btn


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #B07D2E;padding-left:10px;">Unmatched Signals</div>', unsafe_allow_html=True)

    client = db.get_client()
    resp = (
        client.table("signal_review_queue")
        .select("id, extracted_name, best_match_name, match_confidence, reason, created_at, raw_id")
        .eq("rep_id", "brianoneill")
        .eq("reviewed", False)
        .order("created_at", desc=True)
        .execute()
    )
    items = resp.data or []
    all_accounts = db.get_account_names()
    account_options = {a["company_name"]: a["id"] for a in sorted(all_accounts, key=lambda x: x["company_name"])}

    if not items:
        st.info("No unmatched signals.")
        return

    st.markdown(f"**{len(items)} pending review**")
    st.markdown("---")

    for item in items:
        extracted = item.get("extracted_name") or "*(no company name found)*"
        best = item.get("best_match_name") or "—"
        conf = item.get("match_confidence") or 0
        reason = item.get("reason") or ""
        created = (item.get("created_at") or "")[:10]
        raw_id = item.get("raw_id")

        with st.container():
            st.markdown(f"**{extracted}**")
            st.caption(f"Best guess: {best} ({conf:.0f}% confidence) · {reason} · {created}")

            if raw_id:
                raw_resp = client.table("signals_raw").select("file_url, body_text").eq("id", raw_id).execute()
                raw = (raw_resp.data or [{}])[0]
                if raw.get("file_url"):
                    st.markdown(f"[📎 View attachment]({raw['file_url']})")
                elif raw.get("body_text"):
                    with st.expander("View email body"):
                        st.text(raw.get("body_text", "")[:500])

            tag_col, dismiss_col = st.columns([4, 1])
            with tag_col:
                selected_name = st.selectbox(
                    "Tag to account",
                    options=["— select account —"] + list(account_options.keys()),
                    key=f"tag_select_{item['id']}",
                    label_visibility="collapsed",
                )
                if selected_name != "— select account —":
                    if st.button("Confirm tag", key=f"tag_confirm_{item['id']}"):
                        selected_id = account_options[selected_name]
                        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

                        client.table("signal_review_queue").update({
                            "reviewed": True,
                            "resolved_to_account_id": selected_id,
                            "reviewed_at": now_iso,
                        }).eq("id", item["id"]).execute()

                        existing = client.table("signals_processed").select("id").eq("raw_id", raw_id).execute()
                        if existing.data:
                            client.table("signals_processed").update({"account_id": selected_id}).eq("raw_id", raw_id).execute()
                        else:
                            raw_signal = client.table("signals_raw").select("*").eq("id", raw_id).execute()
                            r = (raw_signal.data or [{}])[0]
                            client.table("signals_processed").insert({
                                "raw_id": raw_id,
                                "account_id": selected_id,
                                "rep_id": "brianoneill",
                                "signal_type": "other",
                                "signal_source": "email",
                                "source": "text_forward",
                                "headline": r.get("subject") or "",
                                "summary": item.get("extracted_name") or "",
                                "signal_date": now_iso[:10],
                                "match_confidence": 0,
                                "file_url": r.get("file_url"),
                            }).execute()

                            acct = client.table("accounts").select("signal_count").eq("id", selected_id).single().execute()
                            count = (acct.data or {}).get("signal_count") or 0
                            client.table("accounts").update({
                                "signal_count": count + 1,
                                "last_signal_date": now_iso[:10],
                                "updated_at": now_iso,
                            }).eq("id", selected_id).execute()

                        st.rerun()
            with dismiss_col:
                if st.button("Dismiss", key=f"dismiss_{item['id']}"):
                    client.table("signal_review_queue").update({"reviewed": True}).eq("id", item["id"]).execute()
                    st.rerun()
            st.markdown("---")
