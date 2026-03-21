import duckdb
import streamlit as st
import plotly.express as px
import pandas as pd
from pathlib import Path

from src.queries import (
    get_kpi_metrics, get_daily_sessions,
    get_cost_by_practice_over_time, get_cost_by_level_over_time,
    get_token_breakdown, get_model_distribution, get_cache_hit_rate,
    get_usage_by_practice, get_usage_by_level, get_top_engineers, get_usage_by_location,
    get_hourly_heatmap, get_day_of_week_counts, get_business_hours_split,
    get_tool_frequency, get_tool_accept_reject, get_tool_execution_time,
)

DB_PATH = "db/analytics.duckdb"

st.set_page_config(page_title="Claude Code Analytics", layout="wide")


@st.cache_resource
def get_connection():
    if not Path(DB_PATH).exists():
        st.error(f"Database not found at `{DB_PATH}`. Run `python ingest.py` first.")
        st.stop()
    return duckdb.connect(DB_PATH, read_only=True)


conn = get_connection()

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

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Overview", "Cost & Tokens", "Team & Engineers", "Activity Patterns", "Tool Behavior"]
)

# ── Tab 1: Overview ───────────────────────────────────────────────────────────
with tab1:
    kpis = get_kpi_metrics(conn, filters)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cost",       f"${kpis['total_cost']:,.2f}")
    c2.metric("Total Sessions",   f"{kpis['total_sessions']:,}")
    c3.metric("Active Engineers", kpis["active_engineers"])
    c4.metric("API Error Rate",   f"{kpis['error_rate']:.1%}")

    st.divider()

    df = get_daily_sessions(conn, filters)
    if df.empty:
        st.info("No data for selected filters.")
    else:
        fig = px.line(df, x="date", y="session_count", title="Daily Sessions")
        st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: Cost & Tokens ──────────────────────────────────────────────────────
with tab2:
    col_left, col_right = st.columns([3, 1])

    with col_left:
        df_practice = get_cost_by_practice_over_time(conn, filters)
        if df_practice.empty:
            st.info("No data for selected filters.")
        else:
            fig = px.line(df_practice, x="date", y="total_cost", color="practice",
                          title="Daily Cost by Practice")
            st.plotly_chart(fig, use_container_width=True)

        df_level = get_cost_by_level_over_time(conn, filters)
        if not df_level.empty:
            fig = px.line(df_level, x="date", y="total_cost", color="level",
                          title="Daily Cost by Seniority Level")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        cache_rate = get_cache_hit_rate(conn, filters)
        st.metric("Cache Hit Rate", f"{cache_rate:.1%}")

        df_model = get_model_distribution(conn, filters)
        if not df_model.empty:
            fig = px.pie(df_model, names="model", values="call_count",
                         title="Model Distribution")
            st.plotly_chart(fig, use_container_width=True)

    df_tokens = get_token_breakdown(conn, filters)
    if not df_tokens.empty:
        fig = px.bar(df_tokens, x="token_type", y="total", title="Token Breakdown")
        st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: Team & Engineers ───────────────────────────────────────────────────
with tab3:
    col_left, col_right = st.columns(2)

    with col_left:
        df_practice = get_usage_by_practice(conn, filters)
        if df_practice.empty:
            st.info("No data for selected filters.")
        else:
            fig = px.bar(df_practice, x="practice", y="session_count",
                         title="Sessions by Practice", color="practice")
            st.plotly_chart(fig, use_container_width=True)

        df_location = get_usage_by_location(conn, filters)
        if not df_location.empty:
            fig = px.bar(df_location, x="location", y="session_count",
                         title="Sessions by Location", color="location")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        df_level = get_usage_by_level(conn, filters)
        if not df_level.empty:
            fig = px.bar(df_level, x="level", y="session_count",
                         title="Sessions by Seniority Level")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 10 Engineers by Session Count")
    df_top = get_top_engineers(conn, filters)
    if df_top.empty:
        st.info("No data for selected filters.")
    else:
        st.dataframe(df_top, use_container_width=True)

# ── Tab 4: Activity Patterns ──────────────────────────────────────────────────
with tab4:
    DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    df_heatmap = get_hourly_heatmap(conn, filters)
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
        df_dow = get_day_of_week_counts(conn, filters)
        if not df_dow.empty:
            df_dow["day_of_week"] = pd.Categorical(
                df_dow["day_of_week"], categories=DAY_ORDER, ordered=True
            )
            df_dow = df_dow.sort_values("day_of_week")
            fig = px.bar(df_dow, x="day_of_week", y="session_count",
                         title="Sessions by Day of Week")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        df_bh = get_business_hours_split(conn, filters)
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

    df_freq = get_tool_frequency(conn, filters)
    if df_freq.empty:
        st.info("No data for selected filters.")
    else:
        fig = px.bar(df_freq, x="tool_name", y="call_count",
                     title="Tool Call Frequency", color="tool_name")
        st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        df_ar = get_tool_accept_reject(conn, filters)
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
        df_exec = get_tool_execution_time(conn, filters)
        if not df_exec.empty:
            fig = px.bar(df_exec, x="tool_name", y="avg_duration_ms",
                         title="Avg Execution Time per Tool (ms)")
            st.plotly_chart(fig, use_container_width=True)
