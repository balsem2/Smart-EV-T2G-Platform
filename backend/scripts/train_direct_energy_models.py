"""Train direct 15-minute-to-24-hour weather-aware models with uncertainty."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from app.database import get_engine
from app.ml.direct_forecaster import build_direct_training_frame, direct_feature_columns
from app.ml.energy_forecaster import TARGETS
from app.ml.weather import WEATHER_FIELDS
from app.models import EnergyData


BACKEND_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = BACKEND_DIR / "ml" / "artifacts" / "energy_forecaster.joblib"
REPORT_PATH = BACKEND_DIR / "reports" / "ddm1" / "direct_v3_metrics.json"


def metrics(actual, predicted) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "r2": float(r2_score(actual, predicted)),
    }


def contiguous_training_segments(raw: pd.DataFrame) -> list[pd.DataFrame]:
    breaks = raw.index.to_series().diff().ne(pd.Timedelta(minutes=15)).cumsum()
    groups = [group for _, group in raw.groupby(breaks)]
    complete = [group.dropna() for group in groups]
    complete = [group for group in complete if len(group) >= 10_000]
    if not complete:
        raise ValueError("No complete weather-enriched 15-minute training segment was found")
    return complete


def central_candidates() -> dict[str, object]:
    return {
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=5.0)),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            learning_rate=0.07,
            max_iter=180,
            max_leaf_nodes=31,
            l2_regularization=0.2,
            early_stopping=True,
            random_state=42,
        ),
    }


def main() -> None:
    columns = [getattr(EnergyData, name) for name in ("timestamp", *TARGETS, *WEATHER_FIELDS)]
    raw = pd.read_sql(select(*columns).order_by(EnergyData.timestamp), get_engine(), index_col="timestamp")
    segments = contiguous_training_segments(raw)
    feature_parts, target_parts = zip(*(build_direct_training_frame(segment) for segment in segments))
    features = pd.concat(feature_parts).sort_index()
    targets = pd.concat(target_parts).sort_index()
    train_end = int(len(features) * 0.70)
    validation_end = int(len(features) * 0.85)
    x_train, x_validation, x_test = features.iloc[:train_end], features.iloc[train_end:validation_end], features.iloc[validation_end:]

    models = {}
    lower_models = {}
    upper_models = {}
    interval_corrections = {}
    evaluation_samples = {}
    report = {}
    for target in TARGETS:
        candidates = central_candidates()
        validation_scores = {}
        for name, candidate in candidates.items():
            candidate.fit(x_train, targets[target].iloc[:train_end])
            validation_scores[name] = float(mean_absolute_error(targets[target].iloc[train_end:validation_end], candidate.predict(x_validation)))
        winner = min(validation_scores, key=validation_scores.get)
        model = central_candidates()[winner]
        model.fit(features.iloc[:validation_end], targets[target].iloc[:validation_end])
        prediction = model.predict(x_test)

        interval_models = []
        for quantile in (0.10, 0.90):
            interval_model = HistGradientBoostingRegressor(
                loss="quantile", quantile=quantile, learning_rate=0.07,
                max_iter=120, max_leaf_nodes=31, l2_regularization=0.2,
                early_stopping=True, random_state=42,
            )
            interval_model.fit(x_train, targets[target].iloc[:train_end])
            interval_models.append(interval_model)
        validation_lower = interval_models[0].predict(x_validation)
        validation_upper = interval_models[1].predict(x_validation)
        validation_low = np.minimum(validation_lower, validation_upper)
        validation_high = np.maximum(validation_lower, validation_upper)
        validation_actual = targets[target].iloc[train_end:validation_end].to_numpy()
        nonconformity = np.maximum.reduce((validation_low - validation_actual, validation_actual - validation_high, np.zeros_like(validation_actual)))
        correction = float(np.quantile(nonconformity, 0.80, method="higher"))
        lower = interval_models[0].predict(x_test)
        upper = interval_models[1].predict(x_test)
        low = np.minimum(lower, upper) - correction
        high = np.maximum(lower, upper) + correction
        result = metrics(targets[target].iloc[validation_end:], prediction)
        result["interval_80_coverage"] = float(np.mean((targets[target].iloc[validation_end:] >= low) & (targets[target].iloc[validation_end:] <= high)))
        report[target] = {"selected_model": winner, "validation_mae": validation_scores, "test": result}
        evaluation_samples[target] = [
            {
                "timestamp": timestamp.isoformat(),
                "actual": round(float(actual), 4),
                "predicted": round(float(predicted), 4),
            }
            for timestamp, actual, predicted in zip(
                x_test.index[-96:],
                targets[target].iloc[validation_end:].to_numpy()[-96:],
                prediction[-96:],
            )
        ]
        models[target] = model
        lower_models[target], upper_models[target] = interval_models
        interval_corrections[target] = correction
        print(target, json.dumps(report[target]))

    training_weather = pd.concat(segments).sort_index()
    weather_climatology = training_weather.groupby([training_weather.index.month, training_weather.index.hour * 4 + training_weather.index.minute // 15])[list(WEATHER_FIELDS)].mean()
    climatology = {
        f"{month}-{quarter}": {field: float(row[field]) for field in WEATHER_FIELDS}
        for (month, quarter), row in weather_climatology.iterrows()
    }
    bundle = {
        "model_name": "direct-multihorizon-weather-at-v3",
        "model_type": "direct_multi_horizon",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_start": min(segment.index.min() for segment in segments).isoformat(),
        "data_end": max(segment.index.max() for segment in segments).isoformat(),
        "training_segments": len(segments),
        "training_samples": len(features),
        "metrics_scope": "direct_15_min_to_24_hour",
        "feature_columns": direct_feature_columns(),
        "metrics": report,
        "models": models,
        "lower_models": lower_models,
        "upper_models": upper_models,
        "interval_corrections": interval_corrections,
        "interval_coverage_target": 0.80,
        "weather_climatology": climatology,
        "evaluation_samples": evaluation_samples,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = ARTIFACT_PATH.with_suffix(".joblib.tmp")
    joblib.dump(bundle, temporary_path, compress=3)
    temporary_path.replace(ARTIFACT_PATH)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({key: value for key, value in bundle.items() if key not in {"models", "lower_models", "upper_models", "weather_climatology"}}, indent=2), encoding="utf-8")
    metadata_path = ARTIFACT_PATH.parent / "metadata.json"
    metadata_path.write_text(REPORT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Saved V3 model bundle to {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
