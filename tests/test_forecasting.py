import pandas as pd

from src.forecasting import (
    build_forecast_summary,
    detect_anomalies,
    normalize_daily_costs,
)


def test_normalize_daily_costs_fills_missing_days():
    df = pd.DataFrame(
        {
            "ds": ["2025-12-10", "2025-12-12"],
            "y": [1.5, 2.0],
        }
    )

    result = normalize_daily_costs(df, "2025-12-10", "2025-12-12")

    assert result["ds"].astype(str).tolist() == [
        "2025-12-10",
        "2025-12-11",
        "2025-12-12",
    ]
    assert result["y"].tolist() == [1.5, 0.0, 2.0]


def test_build_forecast_summary_returns_insufficient_data_for_short_series():
    df = pd.DataFrame(
        {
            "ds": pd.date_range("2025-12-01", periods=7, freq="D"),
            "y": [1.0] * 7,
        }
    )

    summary = build_forecast_summary(df, periods=14)

    assert summary["status"] == "insufficient_data"
    assert summary["message"]
    assert summary["forecast"] == []
    assert summary["metrics"] is None
    assert summary["anomalies"] == []


def test_build_forecast_summary_returns_forecast_and_metrics_with_monkeypatched_dependencies(monkeypatch):
    df = pd.DataFrame(
        {
            "ds": pd.date_range("2025-12-01", periods=44, freq="D"),
            "y": [1.0] * 44,
        }
    )
    forecast_frame = pd.DataFrame(
        {
            "ds": pd.date_range("2025-12-01", periods=58, freq="D"),
            "yhat": [1.0] * 58,
            "yhat_lower": [0.9] * 58,
            "yhat_upper": [1.1] * 58,
        }
    )

    monkeypatch.setattr(
        "src.forecasting.fit_prophet_and_predict",
        lambda history, periods=14: (object(), forecast_frame),
    )
    monkeypatch.setattr(
        "src.forecasting._compute_cv_metrics",
        lambda model, history: ({"mae": 0.1, "mape": 0.2, "coverage": 0.9}, None),
    )

    summary = build_forecast_summary(df, periods=14)

    assert summary["status"] == "ok"
    assert len(summary["forecast"]) == 14
    assert summary["metrics"] == {"mae": 0.1, "mape": 0.2, "coverage": 0.9}
    assert summary["anomalies"] == []


def test_build_forecast_summary_returns_error_status_when_model_fails(monkeypatch):
    df = pd.DataFrame(
        {
            "ds": pd.date_range("2025-12-01", periods=21, freq="D"),
            "y": [1.0] * 21,
        }
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.forecasting.fit_prophet_and_predict", boom)

    summary = build_forecast_summary(df, periods=14)

    assert summary["status"] == "forecast_error"
    assert "boom" in summary["message"]
    assert len(summary["history"]) == 21
    assert summary["forecast"] == []
    assert summary["metrics"] is None
    assert summary["anomalies"] == []


def test_build_forecast_summary_runs_real_prophet_forecast_without_cv_metrics():
    df = pd.DataFrame(
        {
            "ds": pd.date_range("2025-12-01", periods=21, freq="D"),
            "y": [float(i % 5) for i in range(21)],
        }
    )

    summary = build_forecast_summary(df, periods=14)

    assert summary["status"] == "ok"
    assert len(summary["forecast"]) == 14
    assert summary["metrics"] is None
    assert summary["message"]


def test_detect_anomalies_returns_expected_fields():
    history = pd.DataFrame(
        {
            "ds": pd.date_range("2025-12-01", periods=5, freq="D"),
            "y": [1.0, 1.0, 11.0, 1.0, 1.0],
            "yhat": [1.0, 1.0, 1.0, 1.0, 1.0],
        }
    )

    rows = detect_anomalies(history)

    assert list(rows.columns) == ["ds", "actual_cost", "expected_cost", "residual"]
    assert len(rows) == 1
    assert rows.iloc[0]["actual_cost"] == 11.0
    assert rows.iloc[0]["expected_cost"] == 1.0


def test_detect_anomalies_returns_empty_frame_when_residual_std_is_zero():
    history = pd.DataFrame(
        {
            "ds": pd.date_range("2025-12-01", periods=4, freq="D"),
            "y": [2.0, 2.0, 2.0, 2.0],
            "yhat": [2.0, 2.0, 2.0, 2.0],
        }
    )

    rows = detect_anomalies(history)

    assert list(rows.columns) == ["ds", "actual_cost", "expected_cost", "residual"]
    assert rows.empty
