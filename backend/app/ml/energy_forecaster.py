from __future__ import annotations

import math
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd


TARGETS = (
    "electricity_price",
    "grid_load",
    "solar_generation",
    "wind_generation",
)
CALENDAR_FEATURES = (
    "quarter_sin",
    "quarter_cos",
    "weekday_sin",
    "weekday_cos",
    "month_sin",
    "month_cos",
    "is_weekend",
)
LAGS = (1, 4, 96, 672)
DAILY_LAGS = (96, 192, 288, 384, 480, 576, 672)
ROLLING_WINDOWS = (4, 96)
ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "energy_forecaster.joblib"
BACKTEST_PATH = Path(__file__).resolve().parents[2] / "reports" / "ddm1" / "recursive_24h_backtest.json"


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    index = result.index
    quarter = index.hour * 4 + index.minute // 15
    result["quarter_sin"] = [math.sin(2 * math.pi * value / 96) for value in quarter]
    result["quarter_cos"] = [math.cos(2 * math.pi * value / 96) for value in quarter]
    result["weekday_sin"] = [math.sin(2 * math.pi * value / 7) for value in index.dayofweek]
    result["weekday_cos"] = [math.cos(2 * math.pi * value / 7) for value in index.dayofweek]
    result["month_sin"] = [math.sin(2 * math.pi * (value - 1) / 12) for value in index.month]
    result["month_cos"] = [math.cos(2 * math.pi * (value - 1) / 12) for value in index.month]
    result["is_weekend"] = (index.dayofweek >= 5).astype(int)
    return result


def build_feature_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    regular = raw.sort_index().asfreq("15min")
    features = add_calendar_features(pd.DataFrame(index=regular.index))
    for target in TARGETS:
        for lag in sorted(set(LAGS + DAILY_LAGS)):
            features[f"{target}_lag_{lag}"] = regular[target].shift(lag)
        shifted = regular[target].shift(1)
        for window in ROLLING_WINDOWS:
            features[f"{target}_rolling_mean_{window}"] = shifted.rolling(window).mean()
    combined = features.join(regular[list(TARGETS)]).dropna()
    return combined[features.columns], combined[list(TARGETS)]


def default_feature_columns() -> list[str]:
    """Return the original autoregressive feature set used by non-solar models."""
    columns = list(CALENDAR_FEATURES)
    for target in TARGETS:
        columns.extend(f"{target}_lag_{lag}" for lag in LAGS)
        columns.extend(
            f"{target}_rolling_mean_{window}" for window in ROLLING_WINDOWS
        )
    return columns


def solar_day_ahead_feature_columns() -> list[str]:
    """Use only observations available for every horizon in the next 24 hours."""
    return list(CALENDAR_FEATURES) + [
        f"solar_generation_lag_{lag}" for lag in DAILY_LAGS
    ]


def target_feature_columns(bundle: dict, target: str) -> list[str]:
    per_target = bundle.get("model_feature_columns")
    if per_target:
        return per_target[target]
    return bundle["feature_columns"]


def build_runtime_feature_values(timestamp: datetime, history: dict) -> dict:
    calendar = add_calendar_features(
        pd.DataFrame(index=pd.DatetimeIndex([timestamp]))
    )
    values = calendar.iloc[0].to_dict()
    for target in TARGETS:
        series = history[target]
        for lag in sorted(set(LAGS + DAILY_LAGS)):
            values[f"{target}_lag_{lag}"] = series[-lag]
        for window in ROLLING_WINDOWS:
            values[f"{target}_rolling_mean_{window}"] = sum(series[-window:]) / window
    return values


def _round_up_to_quarter(value: datetime) -> datetime:
    rounded = value.replace(second=0, microsecond=0)
    remainder = rounded.minute % 15
    if remainder or value.second or value.microsecond:
        rounded += timedelta(minutes=15 - remainder)
    return rounded


@lru_cache(maxsize=1)
def load_bundle() -> dict:
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            "The energy forecasting model has not been trained yet."
        )
    return joblib.load(ARTIFACT_PATH)


def forecast_energy(energy_rows, start: datetime, end: datetime) -> list[dict]:
    bundle = load_bundle()
    ordered = sorted(
        (row for row in energy_rows if row.timestamp is not None),
        key=lambda row: row.timestamp,
    )
    if len(ordered) < max(LAGS + DAILY_LAGS):
        raise ValueError("At least seven days of recent energy history are required.")
    history = {
        target: [float(getattr(row, target)) for row in ordered]
        for target in TARGETS
    }
    timestamp = _round_up_to_quarter(start)
    forecasts = []
    while timestamp < end:
        values = build_runtime_feature_values(timestamp, history)
        point = {"timestamp": timestamp}
        for target in TARGETS:
            feature_row = pd.DataFrame(
                [values], columns=target_feature_columns(bundle, target)
            )
            prediction = float(bundle["models"][target].predict(feature_row)[0])
            if target != "electricity_price":
                prediction = max(0.0, prediction)
            history[target].append(prediction)
            point[target] = prediction
        forecasts.append(point)
        timestamp += timedelta(minutes=15)
    return forecasts


def model_metadata() -> dict:
    bundle = load_bundle()
    metadata = {
        "model_name": bundle["model_name"],
        "trained_at": bundle["trained_at"],
        "data_start": bundle["data_start"],
        "data_end": bundle["data_end"],
        "metrics": bundle["metrics"],
        "metrics_scope": bundle.get("metrics_scope", "one_step_15_minute"),
        "feature_count": len(bundle["feature_columns"]),
        "feature_counts_by_target": {
            target: len(target_feature_columns(bundle, target)) for target in TARGETS
        },
    }
    if BACKTEST_PATH.exists():
        import json

        backtest = json.loads(BACKTEST_PATH.read_text(encoding="utf-8"))
        metadata["recursive_24h_backtest"] = {
            "origins_evaluated": backtest["origins_evaluated"],
            "observations_per_target": backtest["observations_per_target"],
            "baseline": backtest["baseline"],
            "overall": backtest["overall"],
        }
    return metadata
