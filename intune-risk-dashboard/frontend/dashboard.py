"""
dashboard.py — Streamlit frontend for the Intune Device Risk Intelligence Dashboard.

Connects to the FastAPI backend and renders:
- KPI cards: total devices, compliance rate, avg risk score, high-risk count
- Pie chart: risk level distribution
- Bar chart: OS breakdown
- Table: top at-risk devices with drill-down
- Table: non-compliant devices
"""

import os
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Intune Risk Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

RISK_COLORS = {
    "CRITICAL": "#c0392b",
    "HIGH":     "#e67e22",
    "MEDIUM":   "#f1c40f",
    "LOW":      "#27ae60",
    "PASS":     "#2ecc71",
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120)
def fetch_summary():
    r = requests.get(f"{API_BASE}/risk/summary", timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=120)
def fetch_risk_profiles(limit: int = 500):
    r = requests.get(f"{API_BASE}/risk", params={"limit": limit}, timeout=15)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=120)
def fetch_sync_status():
    r = requests.get(f"{API_BASE}/sync/status", timeout=10)
    r.raise_for_status()
    return r.json()


def trigger_sync():
    r = requests.post(f"{API_BASE}/sync", timeout=60)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🛡️ Intune Risk Dashboard")
    st.markdown("---")

    sync_state = fetch_sync_status()
    st.metric("Devices Cached", sync_state.get("total_devices_cached", 0))
    last_sync = sync_state.get("last_synced_at", "Never")
    st.caption(f"Last sync: {last_sync}")

    if st.button("🔄 Sync Now", use_container_width=True):
        with st.spinner("Syncing with Microsoft Graph…"):
            result = trigger_sync()
        st.success(f"Sync complete — {result.get('changed_devices', 0)} device(s) updated.")
        st.cache_data.clear()
        time.sleep(1)
        st.rerun()

    st.markdown("---")
    risk_filter = st.selectbox(
        "Filter by Risk Level",
        ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "PASS"],
    )
    compliance_filter = st.selectbox(
        "Filter by Compliance",
        ["All", "noncompliant", "compliant", "unknown"],
    )

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("Endpoint Risk Intelligence Dashboard")
st.caption("Powered by Microsoft Intune + Graph API")

try:
    summary = fetch_summary()
    profiles_raw = fetch_risk_profiles(limit=500)
except requests.RequestException as e:
    st.error(f"Cannot reach API at {API_BASE}. Make sure the backend is running. Error: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Row
# ---------------------------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Devices",   summary["total_devices"])
col2.metric("Compliance Rate", f"{summary['compliance_rate_pct']}%",
            delta=f"{summary['compliant_count']} compliant",
            delta_color="normal")
col3.metric("Avg Risk Score",  f"{summary['avg_risk_score']}/100")
col4.metric("Non-Compliant",   summary["noncompliant_count"], delta_color="inverse")
col5.metric("High Risk",
            summary["risk_level_distribution"].get("CRITICAL", 0) +
            summary["risk_level_distribution"].get("HIGH", 0),
            delta_color="inverse")

st.markdown("---")

# ---------------------------------------------------------------------------
# Charts row
# ---------------------------------------------------------------------------
chart_col1, chart_col2, chart_col3 = st.columns([1, 1, 1])

with chart_col1:
    st.subheader("Risk Level Distribution")
    risk_dist = summary.get("risk_level_distribution", {})
    if risk_dist:
        fig = px.pie(
            names=list(risk_dist.keys()),
            values=list(risk_dist.values()),
            color=list(risk_dist.keys()),
            color_discrete_map=RISK_COLORS,
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.subheader("OS Breakdown")
    os_dist = summary.get("os_breakdown", {})
    if os_dist:
        fig2 = px.bar(
            x=list(os_dist.values()),
            y=list(os_dist.keys()),
            orientation="h",
            color=list(os_dist.keys()),
        )
        fig2.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False,
                           yaxis_title="", xaxis_title="Devices")
        st.plotly_chart(fig2, use_container_width=True)

with chart_col3:
    st.subheader("Compliance Snapshot")
    comp_data = {
        "Compliant":     summary["compliant_count"],
        "Non-Compliant": summary["noncompliant_count"],
        "Unknown":       summary["unknown_count"],
    }
    fig3 = go.Figure(go.Bar(
        x=list(comp_data.keys()),
        y=list(comp_data.values()),
        marker_color=["#27ae60", "#c0392b", "#95a5a6"],
    ))
    fig3.update_layout(margin=dict(t=0, b=0, l=0, r=0), yaxis_title="Devices")
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Device Table
# ---------------------------------------------------------------------------
st.subheader("Device Risk Profiles")

df = pd.DataFrame(profiles_raw)

if df.empty:
    st.info("No device data available. Run a sync first.")
    st.stop()

# Rename for display
df = df.rename(columns={
    "device_name": "Device", "user_principal_name": "User",
    "operating_system": "OS", "os_version": "OS Version",
    "compliance_state": "Compliance", "risk_score": "Risk Score",
    "risk_level": "Risk Level", "days_since_sync": "Days Since Sync",
    "is_encrypted": "Encrypted", "jail_broken": "Jailbroken",
})

# Apply filters
if risk_filter != "All":
    df = df[df["Risk Level"] == risk_filter]
if compliance_filter != "All":
    df = df[df["Compliance"] == compliance_filter]

# Color code Risk Level
def style_risk(val):
    color = RISK_COLORS.get(str(val), "")
    return f"color: {color}; font-weight: bold;" if color else ""

display_cols = ["Device", "User", "OS", "OS Version", "Compliance",
                "Risk Score", "Risk Level", "Days Since Sync", "Encrypted", "Jailbroken"]
display_cols = [c for c in display_cols if c in df.columns]

styled = df[display_cols].style.map(style_risk, subset=["Risk Level"])
st.dataframe(styled, use_container_width=True, height=450)

st.caption(f"Showing {len(df)} device(s)  |  Stale (>7d): {summary['stale_device_count']}  |  Unencrypted: {summary['unencrypted_count']}")

# ---------------------------------------------------------------------------
# Risk Factor Drill-down
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Risk Factor Drill-Down")
device_names = {p["device_name"]: p for p in profiles_raw}
selected_name = st.selectbox("Select a device to inspect", options=list(device_names.keys()))
if selected_name:
    profile = device_names[selected_name]
    factors = profile.get("risk_factors", [])
    if factors:
        factor_df = pd.DataFrame(factors)[["name", "score_contribution", "description"]]
        factor_df.columns = ["Risk Factor", "Score", "Description"]
        st.dataframe(factor_df, use_container_width=True)
        st.metric("Total Risk Score", f"{profile['risk_score']}/100  [{profile['risk_level']}]")
    else:
        st.success("No risk factors — device is in good standing.")
