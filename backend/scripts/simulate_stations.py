"""Send realistic charger availability events to the Smart EV station API."""

import argparse
import json
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


def request_json(url: str, *, method: str = "GET", body: dict | None = None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if method != "GET":
        headers["X-Station-Key"] = settings.station_api_key
    request = Request(url, data=payload, headers=headers, method=method)
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def simulate_once(api_url: str) -> None:
    stations = request_json(f"{api_url}/stations")
    for station in stations:
        total = station["total_chargers"]
        status = "maintenance" if random.random() < 0.04 else "online"
        available = 0 if status != "online" else random.randint(0, total)
        updated = request_json(
            f"{api_url}/stations/{station['id']}/status",
            method="POST",
            body={
                "total_chargers": total,
                "available_chargers": available,
                "operational_status": status,
                "availability_source": "simulated",
            },
        )
        print(
            f"{updated['station_name']}: "
            f"{updated['available_chargers']}/{updated['total_chargers']} available "
            f"({updated['operational_status']})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            simulate_once(args.api_url.rstrip("/"))
        except (HTTPError, URLError) as error:
            print(f"Simulator error: {error}")
        if args.once:
            break
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
