"""Probe E-Control access without changing station availability in the database.

Run from backend: ..\\.venv\\Scripts\\python.exe -m scripts.check_econtrol_access
"""

import argparse
import csv
from pathlib import Path

from app.config import BACKEND_DIR, settings
from app.econtrol_client import fetch_nearby


def shape(value: object, depth: int = 0) -> str:
    """Summarize response structure without logging station details or secrets."""
    if depth >= 3:
        return type(value).__name__
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{key}: {shape(item, depth + 1)}" for key, item in list(value.items())[:20]
        ) + "}"
    if isinstance(value, list):
        return f"list[{len(value)}]" + (f" of {shape(value[0], depth + 1)}" if value else "")
    return type(value).__name__


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    args = parser.parse_args()
    if (args.latitude is None) != (args.longitude is None):
        parser.error("Provide both --latitude and --longitude")
    if not settings.econtrol_api_key or not settings.econtrol_referer:
        parser.error("Set ECONTROL_API_KEY and ECONTROL_REFERER in backend/.env first")

    if args.latitude is None:
        csv_path = Path(BACKEND_DIR) / "data" / "austria_charging_stations.csv"
        with csv_path.open(encoding="utf-8", newline="") as handle:
            first_station = next(csv.DictReader(handle))
        latitude, longitude = float(first_station["latitude"]), float(first_station["longitude"])
    else:
        latitude, longitude = args.latitude, args.longitude

    payload = fetch_nearby(
        latitude, longitude,
        api_key=settings.econtrol_api_key,
        referer=settings.econtrol_referer,
    )
    print("E-Control API access succeeded. Response structure:")
    print(shape(payload))
    print("No local station availability was changed.")


if __name__ == "__main__":
    main()
