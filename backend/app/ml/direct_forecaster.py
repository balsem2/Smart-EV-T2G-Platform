"""Leakage-safe direct 96-horizon feature engineering for the V3 forecaster."""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pandas as pd

from app.ml.energy_forecaster import CALENDAR_FEATURES, LAGS, ROLLING_WINDOWS, TARGETS, add_calendar_features
from app.ml.weather import WEATHER_FIELDS


MAX_HORIZON = 96


def direct_feature_columns() -> list[str]:
    columns = list(CALENDAR_FEATURES) + ["horizon_step", "horizon_sin", "horizon_cos"]
    for target in TARGETS:
        columns.extend(f"{target}_origin_lag_{lag}" for lag in LAGS)
        columns.extend(f"{target}_origin_mean_{window}" for window in ROLLING_WINDOWS)
        columns.extend((f"{target}_target_lag_96", f"{target}_target_lag_672"))
    columns.extend(f"weather_{field}" for field in WEATHER_FIELDS)
    return columns


def build_direct_training_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use one rotating horizon per target row to cover 1..96 without 96x expansion."""
    regular = raw.sort_index().asfreq("15min")
    required = list(TARGETS) + list(WEATHER_FIELDS)
    if regular[required].isna().any().any():
        raise ValueError("The selected training segment contains missing energy or weather values")
    target_index = np.arange(max(LAGS) + MAX_HORIZON, len(regular))
    horizon = target_index % MAX_HORIZON + 1
    origin_index = target_index - horizon
    timestamps = regular.index[target_index]
    features = add_calendar_features(pd.DataFrame(index=timestamps))
    features["horizon_step"] = horizon
    features["horizon_sin"] = np.sin(2 * math.pi * horizon / MAX_HORIZON)
    features["horizon_cos"] = np.cos(2 * math.pi * horizon / MAX_HORIZON)

    for target in TARGETS:
        values = regular[target].to_numpy(dtype=float)
        for lag in LAGS:
            features[f"{target}_origin_lag_{lag}"] = values[origin_index - lag + 1]
        shifted_rolling = regular[target].rolling(max(ROLLING_WINDOWS)).mean()
        for window in ROLLING_WINDOWS:
            rolling = regular[target].rolling(window).mean().to_numpy(dtype=float)
            features[f"{target}_origin_mean_{window}"] = rolling[origin_index]
        features[f"{target}_target_lag_96"] = values[target_index - 96]
        features[f"{target}_target_lag_672"] = values[target_index - 672]

    for field in WEATHER_FIELDS:
        features[f"weather_{field}"] = regular[field].to_numpy(dtype=float)[target_index]
    targets = regular[list(TARGETS)].iloc[target_index].copy()
    targets.index = timestamps
    return features[direct_feature_columns()], targets


def build_direct_runtime_values(
    timestamp: datetime,
    horizon_step: int,
    history: dict[str, list[float]],
    weather: dict[str, float],
) -> dict[str, float]:
    calendar = add_calendar_features(pd.DataFrame(index=pd.DatetimeIndex([timestamp])))
    values = calendar.iloc[0].to_dict()
    values["horizon_step"] = horizon_step
    values["horizon_sin"] = math.sin(2 * math.pi * horizon_step / MAX_HORIZON)
    values["horizon_cos"] = math.cos(2 * math.pi * horizon_step / MAX_HORIZON)
    for target in TARGETS:
        series = history[target]
        for lag in LAGS:
            values[f"{target}_origin_lag_{lag}"] = series[-lag]
        for window in ROLLING_WINDOWS:
            values[f"{target}_origin_mean_{window}"] = sum(series[-window:]) / window
        values[f"{target}_target_lag_96"] = series[-(97 - horizon_step)]
        values[f"{target}_target_lag_672"] = series[-(673 - horizon_step)]
    for field in WEATHER_FIELDS:
        values[f"weather_{field}"] = weather[field]
    return values
