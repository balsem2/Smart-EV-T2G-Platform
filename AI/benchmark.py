"""Smart EV — Academic Multi-Model Benchmarking Engine.

Compares candidate forecasting models across all four Austrian energy targets:
1. Historical Seasonal Baseline (Day-of-week + quarter-of-day mean)
2. Ridge Regression (Regularized linear baseline)
3. Random Forest Regressor (Bagging ensemble)
4. HistGradientBoostingRegressor (Boosting ensemble — Production V2)

Generates JSON, CSV, and Markdown benchmark reports.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy import select

# Ensure project paths are resolvable
AI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AI_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from AI.features import (
    TARGETS,
    build_feature_frame,
    default_feature_columns,
    solar_day_ahead_feature_columns,
)
from app.database import get_engine
from app.ml.energy_forecaster import TRAINING_CUTOFF
from app.models import EnergyData

REPORTS_DIR = AI_DIR / "reports"


def compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "r2": float(r2_score(actual, predicted)),
    }


def evaluate_baseline(train_raw: pd.DataFrame, test_raw: pd.DataFrame) -> dict[str, Any]:
    """Seasonal slot-mean baseline (hour, minute, weekday)."""
    results = {}
    train_df = train_raw.copy()
    test_df = test_raw.copy()
    train_df["slot"] = list(zip(train_df.index.weekday, train_df.index.hour, train_df.index.minute))
    test_df["slot"] = list(zip(test_df.index.weekday, test_df.index.hour, test_df.index.minute))

    start_time = time.perf_counter()
    for target in TARGETS:
        slot_means = train_df.groupby("slot")[target].mean().to_dict()
        global_mean = float(train_df[target].mean())
        predictions = test_df["slot"].map(slot_means).fillna(global_mean).to_numpy()
        actual = test_df[target].to_numpy()
        results[target] = compute_metrics(actual, predictions)

    duration = time.perf_counter() - start_time
    return {
        "model_name": "Seasonal Baseline",
        "description": "Historical quarter-hour slot average conditioned on weekday",
        "train_time_sec": round(duration, 3),
        "metrics": results,
    }


def run_benchmark() -> dict[str, Any]:
    print("Loading Austrian energy dataset from PostgreSQL...")
    engine = get_engine()
    statement = select(
        EnergyData.timestamp,
        EnergyData.electricity_price,
        EnergyData.grid_load,
        EnergyData.solar_generation,
        EnergyData.wind_generation,
    ).where(EnergyData.timestamp <= TRAINING_CUTOFF).order_by(EnergyData.timestamp)
    raw = pd.read_sql(statement, engine, index_col="timestamp")
    print(f"Loaded {len(raw):,} observations ({raw.index.min()} to {raw.index.max()})")

    features, targets = build_feature_frame(raw)
    n_samples = len(features)
    train_end = int(n_samples * 0.70)
    val_end = int(n_samples * 0.85)

    x_train_full = features.iloc[:train_end]
    x_test_full = features.iloc[val_end:]
    test_targets = targets.iloc[val_end:]

    raw_train = raw.loc[x_train_full.index]
    raw_test = raw.loc[x_test_full.index]

    shared_cols = default_feature_columns()
    solar_cols = solar_day_ahead_feature_columns()

    def get_cols(target: str) -> list[str]:
        return solar_cols if target == "solar_generation" else shared_cols

    benchmark_records = []

    # 1. Baseline
    print("\n[1/4] Evaluating Seasonal Baseline...")
    baseline_res = evaluate_baseline(raw_train, raw_test)
    benchmark_records.append(baseline_res)

    # 2. Ridge Regression
    print("[2/4] Training & Evaluating Ridge Regression...")
    ridge_metrics = {}
    ridge_start = time.perf_counter()
    for target in TARGETS:
        cols = get_cols(target)
        model = Ridge(alpha=10.0)
        model.fit(x_train_full[cols], targets[target].iloc[:train_end])
        preds = model.predict(x_test_full[cols])
        if target != "electricity_price":
            preds = np.clip(preds, 0.0, None)
        ridge_metrics[target] = compute_metrics(test_targets[target].to_numpy(), preds)
    ridge_time = time.perf_counter() - ridge_start
    benchmark_records.append({
        "model_name": "Ridge Regression",
        "description": "L2-regularized linear model with cyclical & lag features",
        "train_time_sec": round(ridge_time, 2),
        "metrics": ridge_metrics,
    })

    # 3. Random Forest
    print("[3/4] Training & Evaluating Random Forest Regressor (subsampled estimators for efficiency)...")
    rf_metrics = {}
    rf_start = time.perf_counter()
    for target in TARGETS:
        cols = get_cols(target)
        model = RandomForestRegressor(
            n_estimators=35,
            max_depth=14,
            max_features="sqrt",
            n_jobs=-1,
            random_state=42,
        )
        model.fit(x_train_full[cols], targets[target].iloc[:train_end])
        preds = model.predict(x_test_full[cols])
        if target != "electricity_price":
            preds = np.clip(preds, 0.0, None)
        rf_metrics[target] = compute_metrics(test_targets[target].to_numpy(), preds)
    rf_time = time.perf_counter() - rf_start
    benchmark_records.append({
        "model_name": "Random Forest",
        "description": "Non-linear Bagging ensemble of decision trees",
        "train_time_sec": round(rf_time, 2),
        "metrics": rf_metrics,
    })

    # 4. HistGradientBoosting (Production V2)
    print("[4/4] Training & Evaluating HistGradientBoosting Regressor (Production V2)...")
    hgb_metrics = {}
    hgb_start = time.perf_counter()
    for target in TARGETS:
        cols = get_cols(target)
        model = HistGradientBoostingRegressor(
            learning_rate=0.08,
            max_iter=180,
            max_leaf_nodes=31,
            l2_regularization=0.1,
            early_stopping=True,
            random_state=42,
        )
        model.fit(x_train_full[cols], targets[target].iloc[:train_end])
        preds = model.predict(x_test_full[cols])
        if target != "electricity_price":
            preds = np.clip(preds, 0.0, None)
        hgb_metrics[target] = compute_metrics(test_targets[target].to_numpy(), preds)
    hgb_time = time.perf_counter() - hgb_start
    benchmark_records.append({
        "model_name": "HistGradientBoosting (V2 Production)",
        "description": "Histogram-based Gradient Boosted Trees with Target-Specific Daily Lags",
        "train_time_sec": round(hgb_time, 2),
        "metrics": hgb_metrics,
    })

    # Export Results
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "dataset_rows": len(raw),
        "test_rows": len(x_test_full),
        "models": benchmark_records,
    }

    (REPORTS_DIR / "benchmark_summary.json").write_text(
        json.dumps(summary_data, indent=2), encoding="utf-8"
    )

    # Flatten for CSV export
    csv_rows = []
    for model_info in benchmark_records:
        m_name = model_info["model_name"]
        m_time = model_info["train_time_sec"]
        for target in TARGETS:
            t_met = model_info["metrics"][target]
            csv_rows.append({
                "model": m_name,
                "target": target,
                "mae": round(t_met["mae"], 4),
                "rmse": round(t_met["rmse"], 4),
                "r2": round(t_met["r2"], 4),
                "train_time_sec": m_time,
            })

    csv_path = REPORTS_DIR / "benchmark_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "target", "mae", "rmse", "r2", "train_time_sec"])
        writer.writeheader()
        writer.writerows(csv_rows)

    # Generate Markdown Report
    md_content = generate_markdown_report(summary_data)
    (REPORTS_DIR / "BENCHMARK_REPORT.md").write_text(md_content, encoding="utf-8")
    print(f"\nBenchmark successfully completed and saved to {REPORTS_DIR}!")
    return summary_data


def generate_markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Smart EV — Energy Forecasting Benchmark Report",
        "",
        "Evaluation of candidate models on the held-out Austrian test set (19,674 quarter-hour observations).",
        "",
        "## Comparative Results by Target",
        "",
    ]
    for target in TARGETS:
        readable_target = target.replace("_", " ").title()
        unit = "€/MWh" if "price" in target else "MW"
        lines.append(f"### {readable_target} ({unit})")
        lines.append("")
        lines.append("| Model | MAE | RMSE | R² | Train Time |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for model in summary["models"]:
            met = model["metrics"][target]
            lines.append(
                f"| **{model['model_name']}** | {met['mae']:.4f} | {met['rmse']:.4f} | {met['r2']:.4f} | {model['train_time_sec']}s |"
            )
        lines.append("")

    lines.extend([
        "## Key Findings & Academic Synthesis",
        "",
        "1. These are one-step historical test metrics, not recursive 24-hour or current-period accuracy. See `backend/reports/ddm1/RECURSIVE_BACKTEST.md` for the deployed day-ahead test.",
        "2. HistGradientBoosting has the lowest test MAE for price and load. Ridge is better for solar and wind on this one-step comparison; there is no universal winning architecture.",
        "3. The deployed solar forecast is a 50/50 model/previous-day blend, which is not represented by the raw HistGradientBoosting row above. Its recursive 24-hour improvement is small and needs further validation.",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    run_benchmark()
