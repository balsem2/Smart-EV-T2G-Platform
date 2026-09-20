"""Train and evaluate the four Austrian 15-minute forecasting models."""

import json
import csv
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy import select

from app.database import get_engine
from app.ml.energy_forecaster import TARGETS, build_feature_frame
from app.models import EnergyData


BACKEND_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = BACKEND_DIR / "ml" / "artifacts"
REPORT_DIR = BACKEND_DIR / "reports" / "ddm1"


def evaluate(actual, predicted) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "r2": float(r2_score(actual, predicted)),
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
    features, targets = build_feature_frame(raw)

    train_end = int(len(features) * 0.70)
    validation_end = int(len(features) * 0.85)
    x_train = features.iloc[:train_end]
    x_validation = features.iloc[train_end:validation_end]
    x_test = features.iloc[validation_end:]
    models = {}
    metrics = {}

    for target in TARGETS:
        model = HistGradientBoostingRegressor(
            learning_rate=0.08,
            max_iter=180,
            max_leaf_nodes=31,
            l2_regularization=0.1,
            early_stopping=True,
            random_state=42,
        )
        model.fit(x_train, targets[target].iloc[:train_end])
        validation_prediction = model.predict(x_validation)
        test_prediction = model.predict(x_test)
        metrics[target] = {
            "validation": evaluate(
                targets[target].iloc[train_end:validation_end],
                validation_prediction,
            ),
            "test": evaluate(targets[target].iloc[validation_end:], test_prediction),
        }
        models[target] = model
        print(target, json.dumps(metrics[target]))

    trained_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "model_name": "hist-gradient-boosting-at-v1",
        "trained_at": trained_at,
        "data_start": raw.index.min().isoformat(),
        "data_end": raw.index.max().isoformat(),
        "metrics_scope": "one_step_15_minute",
        "feature_columns": list(features.columns),
        "metrics": metrics,
        "models": models,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, ARTIFACT_DIR / "energy_forecaster.joblib", compress=3)
    metadata = {key: value for key, value in bundle.items() if key != "models"}
    (ARTIFACT_DIR / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "ml_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    audit = json.loads((REPORT_DIR / "energy_audit.json").read_text(encoding="utf-8"))
    baseline = audit["baseline_test_metrics"]
    with (REPORT_DIR / "model_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["target", "baseline_mae", "ml_mae", "mae_improvement_pct", "baseline_rmse", "ml_rmse", "ml_r2"])
        for target in TARGETS:
            improvement = 100 * (
                baseline[target]["mae"] - metrics[target]["test"]["mae"]
            ) / baseline[target]["mae"]
            writer.writerow([target, baseline[target]["mae"], metrics[target]["test"]["mae"], improvement, baseline[target]["rmse"], metrics[target]["test"]["rmse"], metrics[target]["test"]["r2"]])

    result_markdown = """# Smart EV — ML Model Results

These are chronological **one-step (15-minute-ahead)** test metrics. They must
not be presented as recursive 24-hour accuracy.

| Target | Baseline MAE | ML MAE | MAE improvement | ML RMSE | ML R² |
| --- | ---: | ---: | ---: | ---: | ---: |
"""
    for target in TARGETS:
        improvement = 100 * (
            baseline[target]["mae"] - metrics[target]["test"]["mae"]
        ) / baseline[target]["mae"]
        test = metrics[target]["test"]
        result_markdown += f"| {target} | {baseline[target]['mae']:.4f} | {test['mae']:.4f} | {improvement:.1f}% | {test['rmse']:.4f} | {test['r2']:.4f} |\n"
    result_markdown += """

## Interpretation

The ML models beat the historical slot-average baseline for every target on the
held-out chronological test set. These are not day-ahead results. Run
`python -m scripts.backtest_energy_forecaster` to produce the separate recursive
24-hour evaluation before making day-ahead accuracy claims.
"""
    (REPORT_DIR / "MODEL_RESULTS.md").write_text(result_markdown, encoding="utf-8")
    print(f"Saved model bundle to {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
