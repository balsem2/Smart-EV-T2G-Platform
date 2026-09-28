"""Austrian weather features from Open-Meteo for the energy forecaster.

National generation is represented by the mean of five regional locations
instead of pretending that one Vienna weather station describes all Austria.
All returned timestamps are naive UTC to match ``energy_data.timestamp``.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


WEATHER_FIELDS = (
    "temperature_2m",
    "cloud_cover",
    "shortwave_radiation",
    "wind_speed_100m",
    "precipitation",
)
AUSTRIAN_LOCATIONS = (
    (48.2082, 16.3738),  # Vienna / east
    (47.0707, 15.4395),  # Graz / south-east
    (48.3069, 14.2858),  # Linz / north
    (47.8095, 13.0550),  # Salzburg / west
    (47.2692, 11.4041),  # Innsbruck / alpine west
)


def _request_hourly(base_url: str, latitude: float, longitude: float, start: date, end: date) -> pd.DataFrame:
    params = {
        "latitude": str(latitude),
        "longitude": str(longitude),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(WEATHER_FIELDS),
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }
    request = Request(
        f"{base_url}?{urlencode(params)}",
        headers={"User-Agent": "Smart-EV-academic-project/1.0"},
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    hourly = payload.get("hourly", {})
    timestamps = hourly.get("time", [])
    if not timestamps:
        raise ValueError("Open-Meteo returned no hourly weather observations")
    frame = pd.DataFrame(
        {field: hourly.get(field, [None] * len(timestamps)) for field in WEATHER_FIELDS},
        index=pd.to_datetime(timestamps, utc=True).tz_localize(None),
    )
    return frame.apply(pd.to_numeric, errors="coerce")


def fetch_austrian_weather(start: datetime, end: datetime, *, forecast: bool) -> pd.DataFrame:
    """Return regional-mean weather at 15-minute resolution."""
    base_url = (
        "https://api.open-meteo.com/v1/forecast"
        if forecast
        else "https://archive-api.open-meteo.com/v1/archive"
    )
    frames = [
        _request_hourly(base_url, latitude, longitude, start.date(), end.date())
        for latitude, longitude in AUSTRIAN_LOCATIONS
    ]
    combined = pd.concat(frames, keys=range(len(frames)))
    national = combined.groupby(level=1).mean().sort_index()
    quarter_hourly = national.resample("15min").interpolate(method="time").ffill().bfill()
    return quarter_hourly.loc[(quarter_hourly.index >= start) & (quarter_hourly.index < end)]


_forecast_cache: tuple[datetime, datetime, datetime, dict[datetime, dict[str, float]]] | None = None


def forecast_weather(start: datetime, end: datetime) -> dict[datetime, dict[str, float]]:
    """Fetch and cache the weather forecast used by direct-horizon models."""
    global _forecast_cache
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if _forecast_cache is not None:
        fetched_at, cached_start, cached_end, values = _forecast_cache
        if now - fetched_at < timedelta(minutes=30) and cached_start <= start and cached_end >= end:
            return {timestamp: row for timestamp, row in values.items() if start <= timestamp < end}
    frame = fetch_austrian_weather(start, end, forecast=True)
    values = {
        timestamp.to_pydatetime(): {field: float(row[field]) for field in WEATHER_FIELDS}
        for timestamp, row in frame.iterrows()
    }
    _forecast_cache = (now, start, end, values)
    return values
