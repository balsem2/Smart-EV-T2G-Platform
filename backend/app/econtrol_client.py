"""Read the official Austrian public charging-station API.

This client deliberately does not map the unverified response into availability.
The response schema must be checked with an authenticated sample first.
"""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.e-control.at/charge/1.0"


def fetch_nearby(latitude: float, longitude: float, *, api_key: str, referer: str) -> object:
    """Fetch nearby stations using E-Control's documented public search endpoint."""
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Invalid station coordinates")
    if not api_key.strip():
        raise ValueError("ECONTROL_API_KEY is missing")
    if not referer.startswith("https://"):
        raise ValueError("ECONTROL_REFERER must be the registered HTTPS domain")

    query = urlencode({"latitude": latitude, "longitude": longitude})
    request = Request(
        f"{BASE_URL}/search?{query}",
        headers={
            "Apikey": api_key,
            "Referer": referer,
            "Accept": "application/json",
            "User-Agent": "Smart-EV-academic-project/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)
