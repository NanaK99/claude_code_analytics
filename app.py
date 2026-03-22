import os

import numpy as np
import streamlit as st
import plotly.express as px
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
_API_URL = os.environ.get("API_URL", "http://localhost:8000")
_API_KEY = os.environ.get("API_KEY", "")


def api_post(path: str, filters: dict):
    """POST to the FastAPI backend. Returns parsed JSON or stops on failure."""
    url = f"{_API_URL}{path}"
    try:
        resp = requests.post(url, json=filters, headers={"X-API-Key": _API_KEY}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(
            f"Cannot connect to the API at `{_API_URL}`. "
            "Start it: `conda run -n provectus_task uvicorn api:app --reload`"
        )
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error {resp.status_code}: {resp.json().get('detail', str(e))}")
        st.stop()
    except requests.exceptions.Timeout:
        st.error(f"API request timed out for `{path}`.")
        st.stop()


st.set_page_config(page_title="Claude Code Analytics", layout="wide")

# ── Sidebar Filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Filters")
    date_range = st.date_input(
        "Date Range",
        value=(pd.Timestamp("2025-12-03"), pd.Timestamp("2026-02-01")),
    )
    date_start = str(date_range[0]) if len(date_range) == 2 else "2025-12-03"
    date_end   = str(date_range[1]) if len(date_range) == 2 else "2026-02-01"

    PRACTICES = [
        "Platform Engineering", "Data Engineering", "ML Engineering",
        "Backend Engineering", "Frontend Engineering",
    ]
    selected_practices  = st.multiselect("Practice", PRACTICES, default=[])
    selected_levels     = st.multiselect("Level", [f"L{i}" for i in range(1, 11)], default=[])
    selected_locations  = st.multiselect(
        "Location", ["United States", "Germany", "United Kingdom", "Poland", "Canada"], default=[]
    )

filters = {
    "date_start": date_start, "date_end": date_end,
    "practices": selected_practices,
    "levels":    selected_levels,
    "locations": selected_locations,
}

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("Claude Code Usage Analytics")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Overview", "Cost & Tokens", "Team & Engineers", "Activity Patterns", "Tool Behavior", "Session Intelligence"]
)

# ── Tab 1: Overview ───────────────────────────────────────────────────────────
with tab1:
    kpis = api_post("/api/v1/overview/kpi-metrics", filters)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cost",       f"${kpis['total_cost']:,.2f}")
    c2.metric("Total Sessions",   f"{kpis['total_sessions']:,}")
    c3.metric("Active Engineers", kpis["active_engineers"])
    c4.metric("API Error Rate",   f"{kpis['error_rate']:.1%}")

    session_kpis = api_post("/api/v1/overview/session-kpis", filters)
    c5, c6 = st.columns(2)
    c5.metric("Avg Session Duration", f"{session_kpis['avg_duration_mins']:.1f} min",
              help="Average time from first to last API call within a session")
    c6.metric("Avg Prompts / Session", f"{session_kpis['avg_prompts_per_session']:.1f}")

    st.divider()

    df = pd.DataFrame(api_post("/api/v1/overview/daily-sessions", filters))
    if df.empty:
        st.info("No data for selected filters.")
    else:
        fig = px.line(df, x="date", y="session_count", title="Daily Sessions")
        st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: Cost & Tokens ──────────────────────────────────────────────────────
with tab2:
    col_left, col_right = st.columns([3, 1])

    with col_left:
        df_practice = pd.DataFrame(api_post("/api/v1/costs/by-practice", filters))
        if df_practice.empty:
            st.info("No data for selected filters.")
        else:
            fig = px.line(df_practice, x="date", y="total_cost", color="practice",
                          title="Daily Cost by Practice")
            st.plotly_chart(fig, use_container_width=True)

        df_level = pd.DataFrame(api_post("/api/v1/costs/by-level", filters))
        if not df_level.empty:
            fig = px.line(df_level, x="date", y="total_cost", color="level",
                          title="Daily Cost by Seniority Level")
            st.plotly_chart(fig, use_container_width=True)

        df_avg_cost = pd.DataFrame(api_post("/api/v1/costs/avg-cost-trend", filters))
        if not df_avg_cost.empty:
            fig = px.line(df_avg_cost, x="date", y="avg_cost_per_session",
                          title="Avg Cost per Session (Daily)")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        cache_rate = api_post("/api/v1/costs/cache-hit-rate", filters)["cache_hit_rate"]
        st.metric("Cache Hit Rate", f"{cache_rate:.1%}")

        savings = api_post("/api/v1/overview/cache-savings", filters)["cache_savings_usd"]
        st.metric("~Cache Savings (est.)", f"${savings:,.2f}",
                  help="Estimated savings from prompt caching vs. no-cache baseline. Based on Sonnet 4.6 pricing applied to all models.")

        df_model = pd.DataFrame(api_post("/api/v1/costs/model-distribution", filters))
        if not df_model.empty:
            fig = px.pie(df_model, names="model", values="call_count",
                         title="Model Distribution")
            st.plotly_chart(fig, use_container_width=True)

    df_tokens = pd.DataFrame(api_post("/api/v1/costs/token-breakdown", filters))
    if not df_tokens.empty:
        fig = px.bar(df_tokens, x="token_type", y="total", title="Token Breakdown")
        st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: Team & Engineers ───────────────────────────────────────────────────
with tab3:
    col_left, col_right = st.columns(2)

    with col_left:
        df_practice = pd.DataFrame(api_post("/api/v1/team/by-practice", filters))
        if df_practice.empty:
            st.info("No data for selected filters.")
        else:
            fig = px.bar(df_practice, x="practice", y="session_count",
                         title="Sessions by Practice", color="practice")
            st.plotly_chart(fig, use_container_width=True)

        df_location = pd.DataFrame(api_post("/api/v1/team/by-location", filters))
        if not df_location.empty:
            fig = px.bar(df_location, x="location", y="session_count",
                         title="Sessions by Location", color="location")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        df_level = pd.DataFrame(api_post("/api/v1/team/by-level", filters))
        if not df_level.empty:
            fig = px.bar(df_level, x="level", y="session_count",
                         title="Sessions by Seniority Level")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 10 Engineers by Session Count")
    df_top = pd.DataFrame(api_post("/api/v1/team/top-engineers", filters))
    if df_top.empty:
        st.info("No data for selected filters.")
    else:
        st.dataframe(df_top, use_container_width=True)

# ── Tab 4: Activity Patterns ──────────────────────────────────────────────────
with tab4:
    DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    df_heatmap = pd.DataFrame(api_post("/api/v1/activity/hourly-heatmap", filters))
    if df_heatmap.empty:
        st.info("No data for selected filters.")
    else:
        pivot = (
            df_heatmap
            .pivot_table(index="day_of_week", columns="hour",
                         values="session_count", fill_value=0)
            .reindex([d for d in DAY_ORDER if d in df_heatmap["day_of_week"].unique()])
        )
        fig = px.imshow(
            pivot,
            title="Session Heatmap: Hour of Day × Day of Week",
            labels={"x": "Hour", "y": "Day", "color": "Sessions"},
            color_continuous_scale="Blues",
        )
        st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        df_dow = pd.DataFrame(api_post("/api/v1/activity/day-of-week", filters))
        if not df_dow.empty:
            df_dow["day_of_week"] = pd.Categorical(
                df_dow["day_of_week"], categories=DAY_ORDER, ordered=True
            )
            df_dow = df_dow.sort_values("day_of_week")
            fig = px.bar(df_dow, x="day_of_week", y="session_count",
                         title="Sessions by Day of Week")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        df_bh = pd.DataFrame(api_post("/api/v1/activity/business-hours", filters))
        if not df_bh.empty:
            fig = px.pie(df_bh, names="category", values="session_count",
                         title="Business Hours vs After Hours")
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 5: Tool Behavior ──────────────────────────────────────────────────────
with tab5:
    st.markdown(
        "_Tools like **Write**, **Edit**, **Bash** indicate active code generation; "
        "**Read**, **Grep**, **Glob** indicate exploration._"
    )

    df_freq = pd.DataFrame(api_post("/api/v1/tools/frequency", filters))
    if df_freq.empty:
        st.info("No data for selected filters.")
    else:
        fig = px.bar(df_freq, x="tool_name", y="call_count",
                     title="Tool Call Frequency", color="tool_name")
        st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        df_ar = pd.DataFrame(api_post("/api/v1/tools/accept-reject", filters))
        if not df_ar.empty:
            df_melted = df_ar.melt(
                id_vars="tool_name",
                value_vars=["accept_count", "reject_count"],
                var_name="decision", value_name="count",
            )
            fig = px.bar(df_melted, x="tool_name", y="count", color="decision",
                         barmode="stack", title="Accept vs Reject per Tool")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        df_exec = pd.DataFrame(api_post("/api/v1/tools/execution-time", filters))
        if not df_exec.empty:
            fig = px.bar(df_exec, x="tool_name", y="avg_duration_ms",
                         title="Avg Execution Time per Tool (ms)")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tool Success Rate")
    df_success = pd.DataFrame(api_post("/api/v1/tools/success-rate", filters))
    if not df_success.empty:
        fig = px.bar(df_success, x="success_rate", y="tool_name", orientation="h",
                     title="Tool Success Rate (sorted ascending — lowest first)",
                     labels={"success_rate": "Success Rate", "tool_name": "Tool"})
        fig.update_xaxes(range=[0, 1], tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

# ── Tab 6: Session Intelligence ───────────────────────────────────────────
with tab6:
    st.markdown(
        "_Session-level analysis: duration, cost distribution, API latency, errors, and seniority patterns._"
    )

    col_left, col_right = st.columns(2)

    with col_left:
        df_dur = pd.DataFrame(api_post("/api/v1/sessions/duration-hist", filters))
        if df_dur.empty:
            st.info("No data for selected filters.")
        else:
            df_dur_pos = df_dur[df_dur["duration_mins"] > 0]
            if df_dur_pos.empty:
                st.info("No sessions with measurable duration.")
            else:
                vals = df_dur_pos["duration_mins"].values
                bins = np.logspace(np.log10(vals.min()), np.log10(vals.max()), 31)
                counts, edges = np.histogram(vals, bins=bins)
                bin_centers = np.sqrt(edges[:-1] * edges[1:])
                fig = px.bar(
                    x=bin_centers, y=counts,
                    log_x=True,
                    title="Session Duration Distribution (mins)",
                    labels={"x": "Duration (mins)", "y": "Sessions"},
                )
                st.plotly_chart(fig, use_container_width=True)

        df_lat = pd.DataFrame(api_post("/api/v1/sessions/api-latency", filters))
        if not df_lat.empty:
            fig = px.bar(df_lat, x="avg_duration_ms", y="model", orientation="h",
                         title="Avg API Latency by Model (ms)",
                         labels={"avg_duration_ms": "Avg Latency (ms)", "model": "Model"})
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        df_err = pd.DataFrame(api_post("/api/v1/sessions/error-breakdown", filters))
        if not df_err.empty:
            fig = px.bar(df_err, x="status_code", y="count",
                         title="API Errors by Status Code",
                         labels={"status_code": "Status Code", "count": "Error Count"})
            st.plotly_chart(fig, use_container_width=True)

        df_level_cost = pd.DataFrame(api_post("/api/v1/sessions/level-cost-correlation", filters))
        if not df_level_cost.empty:
            fig = px.bar(df_level_cost, x="level", y="avg_cost_per_session",
                         title="Avg Cost per Session by Seniority Level",
                         labels={"level": "Level", "avg_cost_per_session": "Avg Cost / Session ($)"})
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Session Cost by Practice")
    df_sc = pd.DataFrame(api_post("/api/v1/sessions/cost-by-practice", filters))
    if df_sc.empty:
        st.info("No data for selected filters.")
    else:
        fig = px.box(df_sc, x="practice", y="total_cost",
                     title="Session Cost Distribution by Practice",
                     labels={"practice": "Practice", "total_cost": "Session Cost ($)"})
        st.plotly_chart(fig, use_container_width=True)
