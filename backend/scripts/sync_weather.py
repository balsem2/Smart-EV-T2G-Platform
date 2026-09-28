"""Backfill Austrian regional weather features onto energy observations."""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import bindparam, update

from app.database import get_engine
from app.ml.weather import WEATHER_FIELDS, fetch_austrian_weather
from app.models import EnergyData


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--end", type=datetime.fromisoformat, required=True)
    parser.add_argument("--forecast", action="store_true", help="Use forecast rather than archive API")
    args = parser.parse_args()
    if args.end <= args.start:
        parser.error("--end must be after --start")

    frame = fetch_austrian_weather(args.start, args.end, forecast=args.forecast)
    rows = [
        {
            "row_timestamp": timestamp.to_pydatetime(),
            **{field: float(values[field]) for field in WEATHER_FIELDS},
        }
        for timestamp, values in frame.iterrows()
    ]
    statement = (
        update(EnergyData)
        .where(EnergyData.timestamp == bindparam("row_timestamp"))
        .values(**{field: bindparam(field) for field in WEATHER_FIELDS})
    )
    affected = 0
    with get_engine().begin() as connection:
        for offset in range(0, len(rows), 2_000):
            result = connection.execute(statement, rows[offset : offset + 2_000])
            affected += max(result.rowcount, 0)
    print(f"Weather rows fetched: {len(rows)}; energy observations updated: {affected}")


if __name__ == "__main__":
    main()
