import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.ml.energy_forecaster import MAX_FEED_LAG, forecast_energy, model_metadata
from app.ml.live_prices import fetch_austrian_day_ahead_prices


router = APIRouter(prefix="/ai", tags=["AI"])
VIENNA = ZoneInfo("Europe/Vienna")

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

    feed_is_current = (
        datetime.now(timezone.utc).replace(tzinfo=None) - latest_row.timestamp
        <= MAX_FEED_LAG
    )
    published_prices: dict[datetime, float] = {}
    if feed_is_current:
        try:
            published_prices = fetch_austrian_day_ahead_prices(start_time, end_time)
        except (RuntimeError, ValueError):
            # Keep the ML price forecast available if the public market endpoint is offline.
            published_prices = {}
    for point in forecast_rows:
        published_price = published_prices.get(point["timestamp"])
        if published_price is not None:
            point["electricity_price"] = published_price
            point["price_source"] = "published_day_ahead"
        else:
            point["price_source"] = "ai_forecast"

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
                if "electricity_price_lower" in pt and pt["price_source"] == "ai_forecast" else None
            ),
            "load_interval": (
                [round(pt["grid_load_lower"], 2), round(pt["grid_load_upper"], 2)]
                if "grid_load_lower" in pt else None
            ),
            "weather_source": pt.get("weather_source"),
            "price_source": pt["price_source"],
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

    hourly_groups: dict[str, list[dict]] = {}
    for slot in enhanced_slots:
        local_time = datetime.fromisoformat(slot["timestamp"]).astimezone(VIENNA)
        hour_key = local_time.replace(minute=0, second=0, microsecond=0).isoformat()
        hourly_groups.setdefault(hour_key, []).append(slot)

    hourly_prices = []
    for hour_key, hour_slots in hourly_groups.items():
        average_price = sum(slot["electricity_price"] for slot in hour_slots) / len(hour_slots)
        recommendations = [slot["recommendation"] for slot in hour_slots]
        if recommendations.count("V1G_CHARGE") >= max(1, len(hour_slots) // 2):
            action = "CHARGE"
        elif recommendations.count("V2G_DISCHARGE") >= max(1, len(hour_slots) // 2):
            action = "V2G_EXPORT"
        else:
            action = "WAIT"
        source_count = sum(slot["price_source"] == "published_day_ahead" for slot in hour_slots)
        hourly_prices.append({
            "start_time": hour_slots[0]["timestamp"],
            "end_time": (
                datetime.fromisoformat(hour_slots[-1]["timestamp"]) + timedelta(minutes=15)
            ).isoformat(),
            "austria_hour": hour_key,
            "price_eur_mwh": round(average_price, 2),
            "price_eur_kwh": round(average_price / 1000, 4),
            "action": action,
            "price_source": (
                "published_day_ahead" if source_count == len(hour_slots)
                else "mixed" if source_count else "ai_forecast"
            ),
            "slot_count": len(hour_slots),
        })

    one_hour_windows = []
    for index in range(max(0, len(enhanced_slots) - 3)):
        window = enhanced_slots[index:index + 4]
        timestamps = [datetime.fromisoformat(slot["timestamp"]) for slot in window]
        if any(
            current - previous != timedelta(minutes=15)
            for previous, current in zip(timestamps, timestamps[1:])
        ):
            continue
        one_hour_windows.append({
            "slots": window,
            "score": sum(slot["composite_score"] for slot in window) / 4,
            "price": sum(slot["electricity_price"] for slot in window) / 4,
        })
    best_window = min(one_hour_windows, key=lambda item: item["score"]) if one_hour_windows else None
    peak_window = max(one_hour_windows, key=lambda item: item["price"]) if one_hour_windows else None
    best_charging_window = None
    if best_window is not None:
        window_slots = best_window["slots"]
        confidence_values = [
            slot["confidence_pct"]
            for slot in window_slots
            if slot["confidence_pct"] is not None
        ]
        best_charging_window = {
            "start_time": window_slots[0]["timestamp"],
            "end_time": (
                datetime.fromisoformat(window_slots[-1]["timestamp"]) + timedelta(minutes=15)
            ).isoformat(),
            "average_price_eur_mwh": round(best_window["price"], 2),
            "average_price_eur_kwh": round(best_window["price"] / 1000, 4),
            "price_difference_vs_peak_eur_mwh": round(
                max((peak_window or best_window)["price"] - best_window["price"], 0), 2
            ),
            "average_confidence_pct": (
                round(sum(confidence_values) / len(confidence_values), 1)
                if confidence_values else None
            ),
            "price_source": (
                "published_day_ahead"
                if all(slot["price_source"] == "published_day_ahead" for slot in window_slots)
                else "mixed"
                if any(slot["price_source"] == "published_day_ahead" for slot in window_slots)
                else "ai_forecast"
            ),
            "reason": "Lowest combined price, grid-load and renewable-energy score in the next 24 hours.",
        }

    published_slot_count = sum(
        slot["price_source"] == "published_day_ahead" for slot in enhanced_slots
    )
    if published_slot_count == len(enhanced_slots):
        price_source = "published_day_ahead"
    elif published_slot_count:
        price_source = "mixed"
    else:
        price_source = "ai_forecast"

    return {
        "model_name": meta["model_name"],
        "forecast_mode": "current" if feed_is_current else "historical_demo",
        "price_source": price_source,
        "published_price_slots": published_slot_count,
        "price_unit": "EUR/MWh wholesale market; EUR/kWh is a unit conversion, not a station retail tariff",
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
        "best_charging_window": best_charging_window,
        "hourly_prices": hourly_prices,
        "tips": [
            "Use the recommended one-hour window when your departure time allows it.",
            "The market price is not the final station tariff; check operator fees before payment.",
            "Keep a battery reserve for your next trip instead of always charging to 100%.",
            "Published day-ahead prices are measured market data; load and renewable values remain AI forecasts.",
        ],
        "slots": enhanced_slots,
    }

