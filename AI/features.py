"""Smart EV — AI Feature Engineering & Preprocessing Pipeline.

This module provides reusable feature extraction functions for energy
time-series forecasting:
- Cyclical calendar transforms (quarter of day, day of week, month of year).
- Autoregressive lags (short-term and multi-day).
- Rolling window statistical aggregations.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Sequence

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

# 15-min intervals: 1 = 15m, 4 = 1h, 96 = 24h, 672 = 7 days
LAGS = (1, 4, 96, 672)

# Daily lags for long-range / day-ahead horizon stability (96 = 1d, 192 = 2d, ... 672 = 7d)
DAILY_LAGS = (96, 192, 288, 384, 480, 576, 672)

ROLLING_WINDOWS = (4, 96)


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute cyclical trigonometric transformations for temporal coordinates."""
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


def default_feature_columns() -> list[str]:
    """Features used for electricity price, grid load, and wind generation."""
    columns = list(CALENDAR_FEATURES)
    for target in TARGETS:
        columns.extend(f"{target}_lag_{lag}" for lag in LAGS)
        columns.extend(f"{target}_rolling_mean_{window}" for window in ROLLING_WINDOWS)
    return columns


def solar_day_ahead_feature_columns() -> list[str]:
    """Specialized features for solar generation to avoid recursive feedback degradation."""
    return list(CALENDAR_FEATURES) + [
        f"solar_generation_lag_{lag}" for lag in DAILY_LAGS
    ]


def get_model_feature_columns() -> dict[str, list[str]]:
    """Return the exact feature subset per target."""
    shared = default_feature_columns()
    return {
        target: (
            solar_day_ahead_feature_columns()
            if target == "solar_generation"
            else shared
        )
        for target in TARGETS
    }


def build_feature_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the aligned features and target dataframes from raw energy time-series."""
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


def build_runtime_feature_values(timestamp: datetime, history: dict[str, Sequence[float]]) -> dict[str, float]:
    """Generate dynamic feature dictionary for inference at a specific quarter-hour."""
    calendar = add_calendar_features(
        pd.DataFrame(index=pd.DatetimeIndex([timestamp]))
    )
    values = calendar.iloc[0].to_dict()
    for target in TARGETS:
        series = history[target]
        for lag in sorted(set(LAGS + DAILY_LAGS)):
            values[f"{target}_lag_{lag}"] = float(series[-lag])
        for window in ROLLING_WINDOWS:
            values[f"{target}_rolling_mean_{window}"] = float(
                sum(series[-window:]) / window
            )
    return values
