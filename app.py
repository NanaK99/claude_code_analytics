import os

import numpy as np
import streamlit as st
import plotly.graph_objects as go
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


def fmt_optional_metric(value, kind: str = "number") -> str:
    """Format optional KPI values while keeping missing values readable."""
    if value is None or pd.isna(value):
        return "N/A"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    if kind == "currency":
        return f"${numeric_value:,.2f}"
    if kind == "percent":
        return f"{numeric_value:.1%}" if abs(numeric_value) <= 1 else f"{numeric_value:.1f}%"
    if kind == "integer":
        return f"{numeric_value:,.0f}"
    return f"{numeric_value:,.2f}"


def normalize_forecast_frame(rows: list[dict]) -> pd.DataFrame:
    """Normalize forecast-related API rows into a date-sorted DataFrame."""
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    elif isinstance(rows, (list, tuple)):
        df = pd.DataFrame(rows)
    else:
        return pd.DataFrame()

    if df.empty or "ds" not in df.columns:
        return df
    df = df.copy()
    df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
    df = df[df["ds"].notna()]
    if df.empty:
        return df
    return df.sort_values("ds")


def build_forecast_figure(
    history_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    anomalies_df: pd.DataFrame,
) -> go.Figure | None:
    has_history = not history_df.empty and {"ds", "y"}.issubset(history_df.columns)
    has_forecast = not forecast_df.empty and {"ds", "yhat", "yhat_lower", "yhat_upper"}.issubset(forecast_df.columns)
    has_anomalies = (
        not anomalies_df.empty
        and {"ds", "actual_cost", "expected_cost", "residual"}.issubset(anomalies_df.columns)
    )

    if has_history:
        history_df = history_df.copy()
        history_df["y"] = pd.to_numeric(history_df["y"], errors="coerce")
        history_df = history_df.dropna(subset=["ds", "y"])
        has_history = not history_df.empty

    if has_forecast:
        forecast_df = forecast_df.copy()
        for col in ["yhat", "yhat_lower", "yhat_upper"]:
            forecast_df[col] = pd.to_numeric(forecast_df[col], errors="coerce")
        forecast_df = forecast_df.dropna(subset=["ds", "yhat", "yhat_lower", "yhat_upper"])
        has_forecast = not forecast_df.empty

    if has_anomalies:
        anomalies_df = anomalies_df.copy()
        for col in ["actual_cost", "expected_cost", "residual"]:
            anomalies_df[col] = pd.to_numeric(anomalies_df[col], errors="coerce")
        anomalies_df = anomalies_df.dropna(subset=["ds", "actual_cost", "expected_cost", "residual"])
        has_anomalies = not anomalies_df.empty

    if not any([has_history, has_forecast, has_anomalies]):
        return None

    fig = go.Figure()

    if has_history:
        fig.add_trace(
            go.Scatter(
                x=history_df["ds"],
                y=history_df["y"],
                mode="lines+markers",
                name="Historical cost",
                line=dict(color="#2563eb", width=2.5),
                marker=dict(size=5),
            )
        )

    if has_forecast:
        fig.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat_upper"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat_lower"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(249, 115, 22, 0.18)",
                name="Uncertainty band",
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat"],
                mode="lines",
                name="Forecast",
                line=dict(color="#d97706", width=3, dash="dash"),
            )
        )

    if has_anomalies:
        fig.add_trace(
            go.Scatter(
                x=anomalies_df["ds"],
                y=anomalies_df["actual_cost"],
                mode="markers",
                name="Anomaly",
                marker=dict(color="#dc2626", size=11, symbol="x"),
                customdata=np.stack(
                    [anomalies_df["expected_cost"], anomalies_df["residual"]], axis=-1
                ),
                hovertemplate=(
                    "Date=%{x|%Y-%m-%d}<br>"
                    "Actual=%{y:$,.2f}<br>"
                    "Expected=%{customdata[0]:$,.2f}<br>"
                    "Residual=%{customdata[1]:$,.2f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="Historical Cost, Forecast, and Anomalies",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Cost ($)", tickprefix="$", separatethousands=True)
    return fig


def render_anomaly_table(anomalies_df: pd.DataFrame) -> None:
    required_cols = {"ds", "actual_cost", "expected_cost", "residual"}
    if anomalies_df.empty:
        st.info("No anomalies were flagged for the selected filters.")
        return

    if not required_cols.issubset(anomalies_df.columns):
        st.warning("Anomaly details are unavailable for the current response payload.")
        return

    anomaly_table = anomalies_df.loc[:, ["ds", "actual_cost", "expected_cost", "residual"]].copy()
    anomaly_table["ds"] = pd.to_datetime(anomaly_table["ds"], errors="coerce")
    anomaly_table["actual_cost"] = pd.to_numeric(anomaly_table["actual_cost"], errors="coerce")
    anomaly_table["expected_cost"] = pd.to_numeric(anomaly_table["expected_cost"], errors="coerce")
    anomaly_table["residual"] = pd.to_numeric(anomaly_table["residual"], errors="coerce")
    anomaly_table = anomaly_table.dropna()
    if anomaly_table.empty:
        st.warning("Anomaly details are unavailable for the current response payload.")
        return

    anomaly_table["ds"] = anomaly_table["ds"].dt.strftime("%Y-%m-%d")
    anomaly_table["actual_cost"] = anomaly_table["actual_cost"].map(lambda v: f"${v:,.2f}")
    anomaly_table["expected_cost"] = anomaly_table["expected_cost"].map(lambda v: f"${v:,.2f}")
    anomaly_table["residual"] = anomaly_table["residual"].map(lambda v: f"${v:,.2f}")
    anomaly_table = anomaly_table.rename(
        columns={
            "ds": "Date",
            "actual_cost": "Actual Cost",
            "expected_cost": "Expected Cost",
            "residual": "Residual",
        }
    )
    st.dataframe(anomaly_table, use_container_width=True, hide_index=True)


st.set_page_config(page_title="Claude Code Analytics", layout="wide")

st.markdown(
    """
    <style>
    div[data-baseweb="tab-list"] {
        gap: 0.95rem;
        flex-wrap: wrap;
        margin-bottom: 0.8rem;
    }

    div[data-baseweb="tab-list"] button:nth-child(7),
    div[data-baseweb="tab-list"] button:last-of-type {
        border-radius: 6px !important;
        border: 1px solid rgba(249, 115, 22, 0.45) !important;
        background: rgba(249, 115, 22, 0.12) !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    div[data-baseweb="tab-list"] button:nth-child(7) p,
    div[data-baseweb="tab-list"] button:last-of-type p {
        color: #fb923c !important;
        font-weight: 600 !important;
    }

    div[data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(7),
    div[data-baseweb="tab-list"] button[aria-selected="true"]:last-of-type {
        background: rgba(249, 115, 22, 0.25) !important;
        border-color: rgba(249, 115, 22, 0.7) !important;
    }

    div[data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(7) p,
    div[data-baseweb="tab-list"] button[aria-selected="true"]:last-of-type p {
        color: #fb923c !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "Overview",
        "Cost & Tokens",
        "Team & Engineers",
        "Activity Patterns",
        "Tool Behavior",
        "Session Intelligence",
        "Forecast & Anomalies",
    ]
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

# ── Tab 7: Forecast & Anomalies ───────────────────────────────────────────────
with tab7:
    st.markdown(
        """
        <div style="
            padding: 1.1rem 1.2rem;
            border-radius: 1rem;
            border: 1px solid #fdba74;
            border-left: 8px solid #f97316;
            background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
            box-shadow: 0 14px 30px rgba(249, 115, 22, 0.12);
            color: #7c2d12;
            margin-bottom: 0.9rem;
        ">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;">
                <div>
                    <div style="font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.14em; font-weight: 800; color: #ea580c;">
                        Predictive Analytics
                    </div>
                    <div style="font-size: 1.3rem; font-weight: 800; color: #7c2d12; margin-top: 0.15rem;">
                        Forecast & Anomalies
                    </div>
                </div>
            </div>
            <div style="margin-top: 0.45rem; color: #9a3412; font-size: 1rem;">
                Review the forecasted daily cost, uncertainty range, and flagged anomalies for the selected filters.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    forecast_summary = api_post("/api/v1/forecast/summary", filters)
    status = forecast_summary.get("status", "ok")
    message = forecast_summary.get("message")

    if status == "insufficient_data":
        st.warning(message or "Insufficient daily history to produce a forecast.")
    elif status == "forecast_error":
        st.error(message or "The forecast could not be generated for the selected filters.")
    elif message:
        st.info(message)

    metrics = forecast_summary.get("metrics") or {}
    metric_cols = st.columns(3)
    metric_cols[0].metric("MAPE", fmt_optional_metric(metrics.get("mape"), "percent"))
    metric_cols[1].metric("MAE", fmt_optional_metric(metrics.get("mae"), "currency"))
    metric_cols[2].metric("Coverage", fmt_optional_metric(metrics.get("coverage"), "percent"))

    st.caption("MAPE and coverage are shown as percentages; MAE is shown in cost units.")
    if status == "ok" and metrics.get("mape") is None:
        st.caption("MAPE is only available when cross-validation has non-zero actual-cost days to evaluate.")

    history_df = normalize_forecast_frame(forecast_summary.get("history", []))
    forecast_df = normalize_forecast_frame(forecast_summary.get("forecast", []))
    anomalies_df = normalize_forecast_frame(forecast_summary.get("anomalies", []))

    fig = build_forecast_figure(history_df, forecast_df, anomalies_df)
    if fig is None:
        st.info("No forecast data for the selected filters.")
    else:
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Anomaly Table")
    render_anomaly_table(anomalies_df)
