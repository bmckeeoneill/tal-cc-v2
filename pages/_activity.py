"""Recent activity page."""
import streamlit as st

import db
from pages._shared import go, back_btn


def render():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #3D6B4F;padding-left:10px;">Recent Activity</div>', unsafe_allow_html=True)

    resp = (
        db.get_client()
        .table("signals_processed")
        .select("id, signal_date, account_id, signal_type, headline, signal_source")
        .eq("rep_id", "brianoneill")
        .eq("dismissed", False)
        .order("signal_date", desc=True)
        .execute()
    )
    signals = resp.data or []

    # Fetch account details for enrichment
    acct_resp = (
        db.get_client()
        .table("accounts")
        .select("id, company_name, industry, state, score, nscorp_url")
        .eq("rep_id", "brianoneill")
        .eq("active", True)
        .execute()
    )
    accounts = {a["id"]: a for a in (acct_resp.data or [])}

    if not signals:
        st.info("No undismissed signals.")
        return

    # Header: Company | Actions | Last Signal | Industry | State | Score
    header = st.columns([2, 2, 3, 2, 1, 1])
    for col, h in zip(header, ["Company", "Actions", "Last Signal", "Industry", "State", "Score"]):
        col.markdown(f"**{h}**")
    st.divider()

    all_accounts = db.get_account_names()
    account_options = {a["company_name"]: a["id"] for a in sorted(all_accounts, key=lambda x: x["company_name"])}
    sb = db.get_client()

    for s in signals:
        sig_id = s.get("id")
        account_id = s.get("account_id")
        acct = accounts.get(account_id, {})

        company    = acct.get("company_name") or "—"
        industry   = acct.get("industry") or "—"
        state      = acct.get("state") or "—"
        score      = acct.get("score")
        ns_url     = acct.get("nscorp_url") or ""
        signal_date = (s.get("signal_date") or "")[:10]
        headline   = s.get("headline") or "—"

        cols = st.columns([2, 2, 3, 2, 1, 1])
        cols[0].markdown(f"**{company}**")

        with cols[1]:
            btn_cols = st.columns(3)
            if account_id and btn_cols[0].button("View", key=f"act_view_{sig_id}"):
                st.session_state.selected_account = account_id
                go("account")
            if ns_url:
                btn_cols[1].markdown(
                    f'<a href="{ns_url}" target="_blank" style="display:inline-block;padding:4px 10px;font-size:0.78rem;font-weight:600;background:#E7F2F5;color:#36677D;border:1px solid #b8d4dc;border-radius:6px;text-decoration:none;">NS</a>',
                    unsafe_allow_html=True,
                )
            if btn_cols[2].button("✕", key=f"act_dismiss_{sig_id}", help="Dismiss"):
                db.dismiss_signal(sig_id)
                st.rerun()

        cols[2].write(f"{signal_date} — {headline}")
        cols[3].caption(industry)
        cols[4].caption(state)
        cols[5].caption(str(score) if score is not None else "—")

        with st.expander("Reassign to different account", expanded=False):
            selected_name = st.selectbox(
                "Account",
                options=["— select account —"] + list(account_options.keys()),
                key=f"reassign_select_{sig_id}",
                label_visibility="collapsed",
            )
            if selected_name != "— select account —":
                if st.button("Confirm reassign", key=f"reassign_confirm_{sig_id}"):
                    new_id = account_options[selected_name]
                    sb.table("signals_processed").update({"account_id": new_id}).eq("id", sig_id).execute()
                    st.rerun()
