"""Forecasting helpers for daily cost trends."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics


_HISTORY_MIN_DAYS = 14
_CV_MIN_DAYS = 44
_CV_INITIAL = "29 days"
_CV_PERIOD = "7 days"
_CV_HORIZON = "14 days"
_FORECAST_COLUMNS = ["ds", "yhat", "yhat_lower", "yhat_upper"]
_ANOMALY_COLUMNS = ["ds", "actual_cost", "expected_cost", "residual"]


def _coerce_date(value: Any) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.normalize()
    return pd.to_datetime(value).normalize()


def _empty_history_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["ds", "y"])


def _empty_anomaly_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_ANOMALY_COLUMNS)


def normalize_daily_costs(
    df: pd.DataFrame,
    date_start: Any = None,
    date_end: Any = None,
) -> pd.DataFrame:
    """Normalize a daily cost series over an inclusive date range."""
    if df is None or df.empty:
        if date_start is None or date_end is None:
            return _empty_history_frame()
        start = _coerce_date(date_start)
        end = _coerce_date(date_end)
        if start is None or end is None or start > end:
            return _empty_history_frame()
        idx = pd.date_range(start=start, end=end, freq="D")
        return pd.DataFrame({"ds": idx, "y": [0.0] * len(idx)})

    frame = df.loc[:, ["ds", "y"]].copy()
    frame["ds"] = pd.to_datetime(frame["ds"]).dt.normalize()
    frame["y"] = frame["y"].astype(float)
    frame = frame.groupby("ds", as_index=False)["y"].sum().sort_values("ds")

    start = _coerce_date(date_start) if date_start is not None else frame["ds"].min()
    end = _coerce_date(date_end) if date_end is not None else frame["ds"].max()
    if pd.isna(start) or pd.isna(end) or start > end:
        return _empty_history_frame()

    idx = pd.date_range(start=start, end=end, freq="D")
    normalized = (
        frame.set_index("ds")
        .reindex(idx, fill_value=0.0)
        .rename_axis("ds")
        .reset_index()
    )
    normalized["y"] = normalized["y"].astype(float)
    return normalized.loc[:, ["ds", "y"]]


def fit_prophet_and_predict(history: pd.DataFrame, periods: int = 14) -> tuple[Prophet, pd.DataFrame]:
    """Fit Prophet and return predictions for history plus forward dates."""
    model = Prophet(
        weekly_seasonality=True,
        daily_seasonality=False,
        yearly_seasonality=False,
    )
    model.fit(history.loc[:, ["ds", "y"]])

    future = model.make_future_dataframe(periods=periods, freq="D", include_history=True)
    forecast = model.predict(future).loc[:, _FORECAST_COLUMNS].copy()
    forecast["ds"] = pd.to_datetime(forecast["ds"]).dt.normalize()
    return model, forecast


def detect_anomalies(history_with_fit: pd.DataFrame, sigma_threshold: float = 2.0) -> pd.DataFrame:
    """Flag historical rows whose residual exceeds a residual-based threshold."""
    if history_with_fit is None or history_with_fit.empty:
        return _empty_anomaly_frame()

    frame = history_with_fit.loc[:, ["ds", "y", "yhat"]].copy()
    residuals = frame["y"].astype(float) - frame["yhat"].astype(float)
    residual_std = residuals.std()
    if pd.isna(residual_std) or residual_std == 0:
        return _empty_anomaly_frame()

    mask = residuals.abs() > (sigma_threshold * residual_std)
    if not mask.any():
        return _empty_anomaly_frame()

    anomalies = pd.DataFrame(
        {
            "ds": pd.to_datetime(frame.loc[mask, "ds"]).dt.normalize(),
            "actual_cost": frame.loc[mask, "y"].astype(float).to_numpy(),
            "expected_cost": frame.loc[mask, "yhat"].astype(float).to_numpy(),
            "residual": residuals.loc[mask].astype(float).to_numpy(),
        }
    )
    return anomalies.loc[:, _ANOMALY_COLUMNS]


def _compute_cv_metrics(model: Prophet, history: pd.DataFrame) -> tuple[Optional[dict], Optional[str]]:
    if len(history) < _CV_MIN_DAYS:
        return None, "Cross-validation metrics require at least 44 days of history."

    try:
        cv_df = cross_validation(
            model,
            initial=_CV_INITIAL,
            period=_CV_PERIOD,
            horizon=_CV_HORIZON,
            parallel=None,
        )
        metrics_df = performance_metrics(cv_df)
    except Exception as exc:
        return None, f"Cross-validation metrics unavailable: {exc}"

    if metrics_df.empty:
        return None, "Cross-validation metrics unavailable: no diagnostic rows were returned."

    selected = [column for column in ["mae", "mape", "coverage"] if column in metrics_df.columns]
    metrics = metrics_df.loc[:, selected].mean(numeric_only=True)
    return {
        "mae": None if pd.isna(metrics.get("mae")) else float(metrics.get("mae")),
        "mape": None if pd.isna(metrics.get("mape")) else float(metrics.get("mape")),
        "coverage": None if pd.isna(metrics.get("coverage")) else float(metrics.get("coverage")),
    }, None


def _insufficient_summary(history: pd.DataFrame, message: str) -> dict:
    return {
        "status": "insufficient_data",
        "message": message,
        "history": _frame_to_records(history),
        "forecast": [],
        "metrics": None,
        "anomalies": [],
    }


def _error_summary(history: pd.DataFrame, message: str) -> dict:
    return {
        "status": "forecast_error",
        "message": message,
        "history": _frame_to_records(history),
        "forecast": [],
        "metrics": None,
        "anomalies": [],
    }


def _frame_to_records(frame: pd.DataFrame) -> list[dict]:
    if frame is None or frame.empty:
        return []

    converted = frame.copy()
    if "ds" in converted.columns:
        converted["ds"] = pd.to_datetime(converted["ds"]).dt.date
    return converted.to_dict(orient="records")


def build_forecast_summary(
    df: pd.DataFrame,
    periods: int = 14,
    filters: dict | None = None,
) -> dict:
    """Build the top-level forecasting summary payload."""
    filters = filters or {}
    date_start = filters.get("date_start")
    date_end = filters.get("date_end")

    if df is None or df.empty:
        return _insufficient_summary(
            _empty_history_frame(),
            "No daily cost data is available for the selected filters.",
        )

    history = normalize_daily_costs(df, date_start=date_start, date_end=date_end)
    if history.empty or len(history) < _HISTORY_MIN_DAYS:
        return _insufficient_summary(
            history,
            "At least 14 days of daily cost history are required for forecasting.",
        )

    try:
        model, forecast = fit_prophet_and_predict(history, periods=periods)
    except Exception as exc:
        return _error_summary(
            history,
            f"Forecasting failed: {exc}",
        )

    forecast_history = forecast.iloc[: len(history)].loc[:, ["ds", "yhat"]].copy()
    history_fit = history.merge(forecast_history, on="ds", how="left")
    anomalies = detect_anomalies(history_fit)

    forecast = forecast.loc[forecast["ds"] > history["ds"].max(), _FORECAST_COLUMNS].copy()
    if len(forecast) > periods:
        forecast = forecast.iloc[:periods]

    metrics = None
    metrics_note = None
    if len(history) >= _CV_MIN_DAYS:
        metrics, metrics_note = _compute_cv_metrics(model, history)
    else:
        metrics_note = "Cross-validation metrics require at least 44 days of history."

    return {
        "status": "ok",
        "message": metrics_note,
        "history": _frame_to_records(history),
        "forecast": _frame_to_records(forecast),
        "metrics": metrics,
        "anomalies": _frame_to_records(anomalies),
    }
