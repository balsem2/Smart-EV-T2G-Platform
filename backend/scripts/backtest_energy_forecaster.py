"""Run a leakage-safe recursive 24-hour backtest on the held-out test period."""

from __future__ import annotations

import csv
import json
from datetime import timedelta
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy import select

from app.database import get_engine
from app.ml.energy_forecaster import (
    ARTIFACT_PATH,
    DAILY_LAGS,
    LAGS,
    ROLLING_WINDOWS,
    TARGETS,
    build_runtime_feature_values,
    build_feature_frame,
    predict_target,
)
from app.models import EnergyData


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BACKEND_DIR / "reports" / "ddm1"
FORECAST_STEPS = 96
ORIGIN_SPACING = timedelta(days=7)
SELECTED_HORIZONS = {
    1: "+15 min",
    4: "+1 hour",
    24: "+6 hours",
    48: "+12 hours",
    96: "+24 hours",
}


def evaluate(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "r2": float(r2_score(actual, predicted)),
    }


def build_recursive_forecast(
    bundle: dict,
    regular: pd.DataFrame,
    origin: pd.Timestamp,
) -> list[dict]:
    history_frame = regular.loc[
        origin - timedelta(minutes=15 * max(LAGS + DAILY_LAGS)) :
        origin - timedelta(minutes=15),
        list(TARGETS),
    ]
    history = {
        target: history_frame[target].astype(float).tolist() for target in TARGETS
    }
    rows = []

    for step in range(1, FORECAST_STEPS + 1):
        timestamp = origin + timedelta(minutes=15 * (step - 1))
        values = build_runtime_feature_values(timestamp, history)
        predicted = {}
        for target in TARGETS:
            predicted[target] = predict_target(bundle, target, values)
        for target, value in predicted.items():
            history[target].append(value)

        actual = regular.loc[timestamp]
        baseline = regular.loc[timestamp - timedelta(days=1)]
        for target in TARGETS:
            rows.append(
                {
                    "origin": origin.isoformat(),
                    "timestamp": timestamp.isoformat(),
                    "horizon_step": step,
                    "target": target,
                    "actual": float(actual[target]),
                    "prediction": predicted[target],
                    "seasonal_baseline": float(baseline[target]),
                }
            )
    return rows


def select_origins(
    regular: pd.DataFrame,
    test_start: pd.Timestamp,
) -> list[pd.Timestamp]:
    latest_origin = regular.index.max() - timedelta(minutes=15 * (FORECAST_STEPS - 1))
    candidates = regular.index[
        (regular.index >= test_start)
        & (regular.index <= latest_origin)
        & (regular.index.hour == 0)
        & (regular.index.minute == 0)
    ]
    origins = []
    last_origin = None
    required_history = max(LAGS + DAILY_LAGS)
    for origin in candidates:
        if last_origin is not None and origin - last_origin < ORIGIN_SPACING:
            continue
        window = regular.loc[
            origin - timedelta(minutes=15 * required_history) :
            origin + timedelta(minutes=15 * (FORECAST_STEPS - 1)),
            list(TARGETS),
        ]
        if len(window) != required_history + FORECAST_STEPS or window.isna().any().any():
            continue
        origins.append(origin)
        last_origin = origin
    return origins


def comparison_row(
    target: str,
    scope: str,
    horizon_steps: int,
    horizon_label: str,
    frame: pd.DataFrame,
) -> dict:
    model = evaluate(frame["actual"], frame["prediction"])
    baseline = evaluate(frame["actual"], frame["seasonal_baseline"])
    improvement = (
        100 * (baseline["mae"] - model["mae"]) / baseline["mae"]
        if baseline["mae"]
        else 0.0
    )
    return {
        "target": target,
        "scope": scope,
        "horizon_steps": horizon_steps,
        "horizon_label": horizon_label,
        "observations": int(len(frame)),
        "model_mae": model["mae"],
        "baseline_mae": baseline["mae"],
        "mae_improvement_pct": improvement,
        "model_rmse": model["rmse"],
        "baseline_rmse": baseline["rmse"],
        "model_r2": model["r2"],
        "baseline_r2": baseline["r2"],
    }


def main() -> None:
    statement = select(
        EnergyData.timestamp,
        EnergyData.electricity_price,
        EnergyData.grid_load,
        EnergyData.solar_generation,
        EnergyData.wind_generation,
    ).order_by(EnergyData.timestamp)
    raw = pd.read_sql(statement, get_engine(), index_col="timestamp")
    raw.index = pd.to_datetime(raw.index)
    regular = raw.sort_index().asfreq("15min")
    features, _ = build_feature_frame(raw)
    test_start = features.index[int(len(features) * 0.85)]
    bundle = joblib.load(ARTIFACT_PATH)

    origins = select_origins(regular, test_start)
    if not origins:
        raise RuntimeError("No complete 24-hour test windows were found.")

    records = []
    for number, origin in enumerate(origins, start=1):
        print(f"Backtesting origin {number}/{len(origins)}: {origin.isoformat()}")
        records.extend(build_recursive_forecast(bundle, regular, origin))
    predictions = pd.DataFrame(records)

    comparisons = []
    overall = {}
    horizons = {}
    for target in TARGETS:
        target_frame = predictions[predictions["target"] == target]
        overall_row = comparison_row(
            target, "full_recursive_window", FORECAST_STEPS, "0-24 hours", target_frame
        )
        comparisons.append(overall_row)
        overall[target] = overall_row
        horizons[target] = {}
        for step, label in SELECTED_HORIZONS.items():
            horizon_frame = target_frame[target_frame["horizon_step"] == step]
            row = comparison_row(target, "point_horizon", step, label, horizon_frame)
            comparisons.append(row)
            horizons[target][str(step)] = row

    report = {
        "model_name": bundle["model_name"],
        "solar_blend_weight": bundle.get("solar_blend_weight", 1.0),
        "evaluation_scope": "recursive_24_hour",
        "test_start": test_start.isoformat(),
        "test_end": regular.index.max().isoformat(),
        "origin_spacing_days": int(ORIGIN_SPACING.days),
        "origins_evaluated": len(origins),
        "forecast_steps_per_origin": FORECAST_STEPS,
        "observations_per_target": len(origins) * FORECAST_STEPS,
        "origins": [origin.isoformat() for origin in origins],
        "baseline": "same 15-minute slot from the previous day",
        "overall": overall,
        "selected_horizons": horizons,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "recursive_24h_backtest.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    with (REPORT_DIR / "recursive_24h_backtest.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=list(comparisons[0].keys()))
        writer.writeheader()
        writer.writerows(comparisons)

    markdown = f"""# Recursive 24-hour backtest

This evaluation forecasts all 96 quarter-hour slots recursively: after the first
step, each prediction becomes input to the following step. It therefore measures
the real day-ahead behavior used by Smart EV, without using future observations.

- Held-out test period starts: {test_start.isoformat()}
- Weekly forecast origins evaluated: {len(origins)}
- Predictions per target: {len(origins) * FORECAST_STEPS}
- Baseline: same quarter-hour value from the previous day

| Target | Recursive MAE | Baseline MAE | MAE improvement | Recursive RMSE | R2 |
| --- | ---: | ---: | ---: | ---: | ---: |
"""
    for target in TARGETS:
        row = overall[target]
        markdown += (
            f"| {target} | {row['model_mae']:.4f} | {row['baseline_mae']:.4f} | "
            f"{row['mae_improvement_pct']:.1f}% | {row['model_rmse']:.4f} | "
            f"{row['model_r2']:.4f} |\n"
        )
    markdown += """

## Reading the result

These values are intentionally separate from the one-step 15-minute metrics.
The CSV and JSON reports also include errors at +15 minutes, +1 hour, +6 hours,
+12 hours, and +24 hours so forecast degradation can be inspected by horizon.
The deployed solar value is a 50/50 blend of the V2 model and the previous-day
same-slot observation. Its small gain should not be interpreted as evidence of
reliable live performance; fresh data and further validation are still needed.
"""
    (REPORT_DIR / "RECURSIVE_BACKTEST.md").write_text(markdown, encoding="utf-8")
    print(f"Saved recursive backtest reports to {REPORT_DIR}")


if __name__ == "__main__":
    main()
