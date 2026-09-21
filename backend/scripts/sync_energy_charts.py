"""Import recent Austrian quarter-hour observations from Energy-Charts.

Source: https://api.energy-charts.info/ (CC BY 4.0; energy-charts.info).
The public endpoints are sourced from ENTSO-E/EEX. Price and public power are
joined by UTC timestamp, never by row position.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.import_energy_data import import_rows
from app.ml.energy_forecaster import MAX_FEED_LAG


BASE_URL = "https://api.energy-charts.info/v2"
SOURCE_NAME = "energy-charts.info"


def utc_naive(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source timestamp is missing its UTC offset")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def fetch_series(path: str, params: dict[str, str]) -> dict:
    url = f"{BASE_URL}/{path}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Smart-EV-academic-project/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("country", "at").lower() != "at":
        raise ValueError(f"Unexpected country in {path} response")
    if payload.get("interval_minutes") != 15:
        raise ValueError(f"Expected 15-minute {path} observations")
    if not isinstance(payload.get("data"), list):
        raise ValueError(f"Missing data list in {path} response")
    return payload


def merged_rows(power: dict, price: dict) -> list[dict]:
    if power.get("unit") != "MW" or price.get("unit") != "EUR / MWh":
        raise ValueError("Unexpected Energy-Charts units")
    price_by_time = {
        utc_naive(item["timestamp"]): item.get("values", {}).get("day_ahead_price")
        for item in price["data"]
    }
    rows = []
    for item in power["data"]:
        timestamp = utc_naive(item["timestamp"])
        values = item.get("values", {})
        fields = {
            "electricity_price": price_by_time.get(timestamp),
            "grid_load": values.get("load"),
            "solar_generation": values.get("solar"),
            "wind_generation": values.get("wind_onshore"),
        }
        if any(value is None for value in fields.values()):
            continue
        numeric = {name: float(value) for name, value in fields.items()}
        if not all(math.isfinite(value) for value in numeric.values()):
            continue
        if any(numeric[name] < 0 for name in ("grid_load", "solar_generation", "wind_generation")):
            continue
        rows.append({"timestamp": timestamp, **numeric})
    rows.sort(key=lambda row: row["timestamp"])
    if len({row["timestamp"] for row in rows}) != len(rows):
        raise ValueError("Duplicate timestamps in joined source data")
    return rows


def latest_contiguous_window(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    window = [rows[-1]]
    for row in reversed(rows[:-1]):
        if window[-1]["timestamp"] - row["timestamp"] != timedelta(minutes=15):
            break
        window.append(row)
    return list(reversed(window))


def sync_once(days: int, dry_run: bool) -> None:
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=days)).isoformat()
    end = today.isoformat()
    power = fetch_series("public_power", {"country": "at", "start": start, "end": end})
    price = fetch_series("price", {"bzn": "AT", "start": start, "end": end})
    rows = merged_rows(power, price)
    window = latest_contiguous_window(rows)
    if not window:
        raise RuntimeError("Energy-Charts returned no matching complete Austrian rows")
    age = datetime.now(timezone.utc).replace(tzinfo=None) - window[-1]["timestamp"]
    print(f"Source: {SOURCE_NAME}; rows: {len(rows)}; latest contiguous: {len(window)}")
    print(f"Latest UTC observation: {window[-1]['timestamp'].isoformat()}; age: {age}")
    if len(window) < 672:
        raise RuntimeError("Fewer than 672 consecutive 15-minute rows; live forecast is not ready")
    if age > MAX_FEED_LAG:
        raise RuntimeError("Latest source observation is over three hours old; refusing live import")
    if dry_run:
        print("Dry run: no database changes")
        return
    print(f"Imported/upserted {import_rows(window)} recent Austrian rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watch", action="store_true", help="Repeat every 15 minutes")
    args = parser.parse_args()
    if not 1 <= args.days <= 30:
        parser.error("--days must be between 1 and 30")
    if args.watch and args.dry_run:
        parser.error("--watch and --dry-run cannot be combined")
    if not args.watch:
        sync_once(args.days, args.dry_run)
        return
    print("Watching Austrian Energy-Charts every 15 minutes; press Ctrl+C to stop")
    while True:
        try:
            sync_once(args.days, False)
        except Exception as error:
            print(f"Energy sync failed: {error}", flush=True)
        time.sleep(15 * 60)


if __name__ == "__main__":
    main()
