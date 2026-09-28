"""Published Austrian day-ahead market prices used by the AI recommendation API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.client import IncompleteRead
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


PRICE_URL = "https://api.energy-charts.info/v2/price"
VIENNA = ZoneInfo("Europe/Vienna")


def parse_price_payload(
    payload: dict,
    start: datetime,
    end: datetime,
) -> dict[datetime, float]:
    """Validate a response and normalize its timestamps to naive UTC."""
    if payload.get("country", "at").lower() != "at":
        raise ValueError("Energy-Charts returned prices for an unexpected country.")
    if payload.get("unit") != "EUR / MWh":
        raise ValueError("Energy-Charts returned an unexpected price unit.")
    if payload.get("interval_minutes") != 15:
        raise ValueError("Energy-Charts price resolution is not 15 minutes.")
    if not isinstance(payload.get("data"), list):
        raise ValueError("Energy-Charts response has no price data list.")

    prices: dict[datetime, float] = {}
    for item in payload["data"]:
        timestamp = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Energy-Charts price timestamp has no timezone.")
        timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        value = float(item.get("values", {}).get("day_ahead_price"))
        if start <= timestamp < end and math.isfinite(value):
            prices[timestamp] = value
    return prices


def fetch_austrian_day_ahead_prices(
    start: datetime,
    end: datetime,
    timeout: int = 15,
) -> dict[datetime, float]:
    """Fetch every published price overlapping a UTC-naive forecast horizon."""
    start_utc = start.replace(tzinfo=timezone.utc)
    end_utc = end.replace(tzinfo=timezone.utc)
    first_day = start_utc.astimezone(VIENNA).date()
    last_day = (end_utc - timedelta(microseconds=1)).astimezone(VIENNA).date()
    day = first_day
    prices: dict[datetime, float] = {}

    while day <= last_day:
        params = urlencode({
            "bzn": "AT",
            "start": day.isoformat(),
            "end": (day + timedelta(days=1)).isoformat(),
        })
        request = Request(
            f"{PRICE_URL}?{params}",
            headers={"User-Agent": "Smart-EV-academic-project/1.0"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except HTTPError as error:
            if error.code in (404, 422):
                day += timedelta(days=1)
                continue
            raise RuntimeError(f"Energy-Charts price request failed ({error.code}).") from error
        except (IncompleteRead, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError("Energy-Charts price request failed.") from error
        prices.update(parse_price_payload(payload, start, end))
        day += timedelta(days=1)
    return prices
