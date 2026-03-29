"""TAL Changes and Best Targets pages (mock data)."""
import streamlit as st

import mock_data
from pages._shared import back_btn, score_badge


def render_changes():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">TAL Changes</div>', unsafe_allow_html=True)

    rows_html = ""
    for item in mock_data.MOCK_CHANGES:
        rows_html += f"""
        <tr>
            <td style="color:#667085;">{item['date']}</td>
            <td><strong>{item['company']}</strong></td>
            <td>{item['change']}</td>
            <td style="color:#667085;">{item['reason']}</td>
        </tr>"""

    st.markdown(f"""
    <table class="ps-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Company</th>
                <th>Change</th>
                <th>Reason</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)


def render_targets():
    back_btn("← Home", "home")
    st.markdown('<div class="page-heading">Best Targets</div>', unsafe_allow_html=True)

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
