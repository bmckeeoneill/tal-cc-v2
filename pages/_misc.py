"""TAL Changes and Best Targets pages."""
import streamlit as st

import db
import mock_data
from pages._shared import back_btn, score_badge


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
    st.markdown('<div class="page-heading" style="border-left:4px solid #3D6B4F;padding-left:10px;">Best Targets</div>', unsafe_allow_html=True)

    rows_html = ""
    for item in mock_data.MOCK_TARGETS:
        badge_cls = "score-high" if item["score"] >= 50 else "score-mid" if item["score"] >= 25 else "score-low"
        rows_html += f"""
        <tr>
            <td style="color:#667085;text-align:center;">#{item['rank']}</td>
            <td><strong>{item['company']}</strong></td>
            <td>{item['state']}</td>
            <td>{item['vertical']}</td>
            <td><span class="score-badge {badge_cls}">{item['score']}</span></td>
            <td style="color:#667085;">{item['reason']}</td>
        </tr>"""

    st.markdown(f"""
    <table class="ps-table">
        <thead>
            <tr>
                <th style="text-align:center;">#</th>
                <th>Company</th>
                <th>State</th>
                <th>Vertical</th>
                <th>Score</th>
                <th>Why</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)
