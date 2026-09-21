import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.ml.energy_forecaster import MAX_FEED_LAG, forecast_energy, model_metadata


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
        },
        "slots": enhanced_slots,
    }
