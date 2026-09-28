import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.ml.energy_forecaster import MAX_FEED_LAG, forecast_energy, model_metadata
from app.models import Station, StationAvailabilityObservation


router = APIRouter(prefix="/ai", tags=["AI"])

BENCHMARK_REPORT_PATH = (
    Path(__file__).resolve().parents[3] / "AI" / "reports" / "benchmark_summary.json"
)


@router.get("/model-info")
def get_model_info() -> dict:
    try:
        return model_metadata()
    except FileNotFoundError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            str(error),
        ) from error


@router.get("/benchmark")
def get_benchmark_report() -> dict:
    if not BENCHMARK_REPORT_PATH.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Benchmark summary report not found. Run 'python AI/benchmark.py' first.",
        )
    try:
        return json.loads(BENCHMARK_REPORT_PATH.read_text(encoding="utf-8"))
    except Exception as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Failed to read benchmark report: {error}",
        ) from error


@router.get("/forecast-24h")
def get_24h_forecast(
    start_iso: str | None = Query(
        None, description="Optional ISO start time. Defaults to latest energy data timestamp."
    ),
    database_session: Session = Depends(get_db),
) -> dict:
    energy_rows = crud.list_recent_energy_data(database_session, limit=3000)
    if not energy_rows:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Energy history database is empty.",
        )

    latest_row = max(energy_rows, key=lambda row: row.timestamp)

    if start_iso:
        try:
            start_time = datetime.fromisoformat(start_iso)
            if start_time.tzinfo is not None:
                start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid start_iso format: {error}",
            ) from error
    else:
        # Pick the latest available timestamp in dataset so we have full ground truth context
        start_time = latest_row.timestamp + timedelta(minutes=15)

    end_time = start_time + timedelta(hours=24)

    try:
        forecast_rows = forecast_energy(energy_rows, start_time, end_time)
        meta = model_metadata()
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except Exception as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Forecast failed: {error}",
        ) from error

    if not forecast_rows:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "No forecast points were generated.",
        )

    # Calculate normalization metrics and composite score for each slot
    prices = [pt["electricity_price"] for pt in forecast_rows]
    loads = [pt["grid_load"] for pt in forecast_rows]
    renewables = [pt["solar_generation"] + pt["wind_generation"] for pt in forecast_rows]

    min_p, max_p = min(prices), max(prices)
    min_l, max_l = min(loads), max(loads)
    min_r, max_r = min(renewables), max(renewables)

    def norm(val, lo, hi):
        return 0.0 if hi == lo else (val - lo) / (hi - lo)

    enhanced_slots = []
    for pt in forecast_rows:
        price = pt["electricity_price"]
        load = pt["grid_load"]
        solar = pt["solar_generation"]
        wind = pt["wind_generation"]
        renewable = solar + wind
        score = (
            0.55 * norm(price, min_p, max_p)
            + 0.30 * norm(load, min_l, max_l)
            - 0.15 * norm(renewable, min_r, max_r)
        )
        enhanced_slots.append({
            "timestamp": pt["timestamp"].replace(tzinfo=timezone.utc).isoformat(),
            "electricity_price": round(price, 2),
            "grid_load": round(load, 2),
            "solar_generation": round(solar, 2),
            "wind_generation": round(wind, 2),
            "renewable_total": round(renewable, 2),
            "composite_score": round(score, 4),
            "confidence_pct": round(pt.get("confidence", 0.0) * 100, 1) if "confidence" in pt else None,
            "price_interval": (
                [round(pt["electricity_price_lower"], 2), round(pt["electricity_price_upper"], 2)]
                if "electricity_price_lower" in pt else None
            ),
            "load_interval": (
                [round(pt["grid_load_lower"], 2), round(pt["grid_load_upper"], 2)]
                if "grid_load_lower" in pt else None
            ),
            "weather_source": pt.get("weather_source"),
            "score_factors": {
                "price": round(0.55 * norm(price, min_p, max_p), 4),
                "grid_load": round(0.30 * norm(load, min_l, max_l), 4),
                "renewable_credit": round(-0.15 * norm(renewable, min_r, max_r), 4),
            },
        })

    # Sort to determine optimal charge & discharge opportunities
    scores = sorted(enhanced_slots, key=lambda s: s["composite_score"])
    low_score_threshold = scores[int(len(scores) * 0.25)]["composite_score"]
    top_price = max(prices)

    for slot in enhanced_slots:
        if slot["composite_score"] <= low_score_threshold:
            slot["recommendation"] = "V1G_CHARGE"
        elif slot["electricity_price"] >= top_price * 0.90:
            slot["recommendation"] = "V2G_DISCHARGE"
        else:
            slot["recommendation"] = "STANDARD"
        if slot["recommendation"] == "V1G_CHARGE":
            slot["explanation"] = "Recommended because its combined price and grid pressure are among the lowest 25% of the next 24 hours."
        elif slot["recommendation"] == "V2G_DISCHARGE":
            slot["explanation"] = "Potential V2G opportunity because the predicted market price is within 90% of today's peak."
        else:
            slot["explanation"] = "Neither cheap enough for preferred charging nor valuable enough for V2G export."

    return {
        "model_name": meta["model_name"],
        "forecast_mode": (
            "historical_demo"
            if datetime.now(timezone.utc).replace(tzinfo=None) - latest_row.timestamp
            > MAX_FEED_LAG
            else "current"
        ),
        "last_observed_at": latest_row.timestamp.replace(tzinfo=timezone.utc).isoformat(),
        "start_time": start_time.replace(tzinfo=timezone.utc).isoformat(),
        "end_time": end_time.replace(tzinfo=timezone.utc).isoformat(),
        "slot_count": len(enhanced_slots),
        "summary": {
            "avg_price_eur_mwh": round(sum(prices) / len(prices), 2),
            "min_price_eur_mwh": round(min_p, 2),
            "max_price_eur_mwh": round(max_p, 2),
            "avg_load_mw": round(sum(loads) / len(loads), 2),
            "total_renewable_mwh": round(sum(renewables) * 0.25, 2),
            "solar_peak_mw": round(max(pt["solar_generation"] for pt in forecast_rows), 2),
            "wind_peak_mw": round(max(pt["wind_generation"] for pt in forecast_rows), 2),
            "average_confidence_pct": (
                round(sum(pt.get("confidence", 0.0) for pt in forecast_rows) / len(forecast_rows) * 100, 1)
                if any("confidence" in pt for pt in forecast_rows) else None
            ),
        },
        "slots": enhanced_slots,
    }


@router.get("/stations/{station_id}/availability-24h")
def station_availability_forecast(
    station_id: int,
    database_session: Session = Depends(get_db),
) -> dict:
    """Train only when sufficient real/simulator telemetry exists; never fabricate occupancy AI."""
    station = database_session.get(Station, station_id)
    if station is None or not station.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active station not found.")
    observations = list(database_session.scalars(
        select(StationAvailabilityObservation)
        .where(StationAvailabilityObservation.station_id == station_id)
        .order_by(StationAvailabilityObservation.observed_at)
    ))
    required = 192
    if len(observations) < required:
        return {
            "ready": False,
            "station_id": station_id,
            "observations": len(observations),
            "required_observations": required,
            "reason": "Not enough timestamped occupancy telemetry. Current availability is shown, but no AI probability is invented.",
        }

    timestamps = pd.DatetimeIndex([row.observed_at for row in observations])
    quarters = timestamps.hour * 4 + timestamps.minute // 15
    features = pd.DataFrame({
        "quarter_sin": np.sin(2 * math.pi * quarters / 96),
        "quarter_cos": np.cos(2 * math.pi * quarters / 96),
        "weekday_sin": np.sin(2 * math.pi * timestamps.dayofweek / 7),
        "weekday_cos": np.cos(2 * math.pi * timestamps.dayofweek / 7),
        "is_weekend": (timestamps.dayofweek >= 5).astype(int),
    })
    target = np.array([row.available_chargers / max(row.total_chargers, 1) for row in observations])
    split = max(int(len(features) * 0.8), 1)
    model = HistGradientBoostingRegressor(max_iter=100, random_state=42)
    model.fit(features.iloc[:split], target[:split])
    validation_mae = float(mean_absolute_error(target[split:], model.predict(features.iloc[split:]))) if split < len(features) else None
    model.fit(features, target)
    start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start += timedelta(minutes=(15 - start.minute % 15) % 15)
    future = pd.date_range(start=start.replace(tzinfo=None), periods=96, freq="15min")
    future_quarters = future.hour * 4 + future.minute // 15
    future_features = pd.DataFrame({
        "quarter_sin": np.sin(2 * math.pi * future_quarters / 96),
        "quarter_cos": np.cos(2 * math.pi * future_quarters / 96),
        "weekday_sin": np.sin(2 * math.pi * future.dayofweek / 7),
        "weekday_cos": np.cos(2 * math.pi * future.dayofweek / 7),
        "is_weekend": (future.dayofweek >= 5).astype(int),
    })
    prediction = np.clip(model.predict(future_features), 0, 1)
    return {
        "ready": True,
        "station_id": station_id,
        "observations": len(observations),
        "validation_mae": round(validation_mae, 4) if validation_mae is not None else None,
        "slots": [
            {"timestamp": timestamp.replace(tzinfo=timezone.utc).isoformat(), "availability_probability_pct": round(float(value) * 100, 1)}
            for timestamp, value in zip(future, prediction)
        ],
    }
