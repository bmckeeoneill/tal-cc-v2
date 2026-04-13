"""TAL Changes and Best Targets pages."""
import streamlit as st

import db
from pages._shared import go, back_btn, score_badge


def render_changes():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #3D6B4F;padding-left:10px;">TAL Changes</div>', unsafe_allow_html=True)

    new_accounts = db.get_new_unassigned_accounts()
    inactive_accounts = db.get_inactive_accounts()

    # ── New Accounts ──────────────────────────────────────────────────────────
    st.markdown(f"**New Accounts** — {len(new_accounts)} need acknowledgment")
    if not new_accounts:
        st.caption("No new accounts.")
    else:
        for a in new_accounts:
            c1, c2 = st.columns([5, 1])
            with c1:
                date_str = (a.get("created_at") or "")[:10]
                industry = a.get("industry") or "—"
                state = a.get("state") or "—"
                st.markdown(f"**{a['company_name']}** · {industry} · {state} · Added {date_str}")
            with c2:
                if st.button("Assigned", key=f"assign_{a['id']}"):
                    db.mark_assigned(a["id"])
                    st.rerun()
            st.markdown("---")

    # ── Removed Accounts ──────────────────────────────────────────────────────
    st.markdown(f"**Removed Accounts** — {len(inactive_accounts)} dropped off TAL")
    if not inactive_accounts:
        st.caption("No removed accounts.")
    else:
        rows_html = ""
        for a in inactive_accounts:
            date_str = (a.get("updated_at") or "")[:10]
            rows_html += f"""
            <tr>
                <td><strong>{a['company_name']}</strong></td>
                <td style="color:#667085;">{a.get('industry') or '—'}</td>
                <td style="color:#667085;">{a.get('state') or '—'}</td>
                <td style="color:#667085;">{date_str}</td>
            </tr>"""
        st.markdown(f"""
        <table class="ps-table">
            <thead><tr><th>Company</th><th>Industry</th><th>State</th><th>Removed</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        """, unsafe_allow_html=True)


def render_targets():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #3D6B4F;padding-left:10px;">⭐ Top Targets</div>', unsafe_allow_html=True)

    starred = db.get_starred_accounts()

    if not starred:
        st.caption("No starred accounts yet. Star accounts from the TAL list to add them here.")
        return

    st.caption(f"{len(starred)} starred accounts")

    header_cols = st.columns([0.5, 3, 1, 1, 2, 2, 1])
    for col, h in zip(header_cols, ["", "Company", "State", "Score", "Industry", "Last Signal", "Action"]):
        col.markdown(f"**{h}**")
    st.divider()

    for acct in starred:
        cols = st.columns([0.5, 3, 1, 1, 2, 2, 1])
        acct_id = acct["id"]

        with cols[0]:
            if st.button("★", key=f"star_t_{acct_id}", help="Remove from Top Targets",
                         use_container_width=False):
                db.toggle_starred(acct_id, False)
                st.rerun()

        s = acct.get("score") or 0
        signal_date = acct.get("last_signal_date") or ""
        signal_date_str = str(signal_date)[:10] if signal_date else "—"

        with cols[1]:
            domain = acct.get("domain") or ""
            name = acct.get("company_name") or "—"
            if domain:
                st.markdown(f"**[{name}](https://{domain})**")
            else:
                st.markdown(f"**{name}**")
        with cols[2]:
            st.write(acct.get("state") or "—")
        with cols[3]:
            st.markdown(score_badge(s), unsafe_allow_html=True)
        with cols[4]:
            st.write(acct.get("industry") or "—")
        with cols[5]:
            sc = acct.get("signal_count") or 0
            st.caption(f"{sc} signals · {signal_date_str}")
        with cols[6]:
            if st.button("View", key=f"view_t_{acct_id}"):
                st.session_state.selected_account = acct_id
                go("account")


def render_chop_block():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading" style="border-left:4px solid #9B2335;padding-left:10px;">🪓 Chop Block</div>', unsafe_allow_html=True)

    accounts = db.get_chop_block_accounts()

    if not accounts:
        st.info("No accounts on the Chop Block. Mark accounts for removal from their record page.")
        return

    st.caption(f"{len(accounts)} accounts marked for removal")

    header_cols = st.columns([3, 1, 1, 2, 2, 1])
    for col, h in zip(header_cols, ["Company", "State", "Signals", "Industry", "Last Signal", "Action"]):
        col.markdown(f"**{h}**")
    st.divider()

    for acct in accounts:
        acct_id = acct["id"]
        cols = st.columns([3, 1, 1, 2, 2, 1])
        signal_date_str = str(acct.get("last_signal_date") or "")[:10] or "—"
        sc = acct.get("signal_count") or 0

        with cols[0]:
            domain = acct.get("domain") or ""
            name = acct.get("company_name") or "—"
            if domain:
                st.markdown(f"**[{name}](https://{domain})**")
            else:
                st.markdown(f"**{name}**")
        with cols[1]:
            st.write(acct.get("state") or "—")
        with cols[2]:
            st.write(str(sc))
        with cols[3]:
            st.write(acct.get("industry") or "—")
        with cols[4]:
            st.caption(signal_date_str)
        with cols[5]:
            if st.button("View", key=f"chop_view_{acct_id}"):
                st.session_state.selected_account = acct_id
                go("account")
