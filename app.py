"""
VoltHub T2G — platform API + web server (pure Python stdlib, no dependencies!)
Run:  python3 app.py   ->  http://localhost:5000
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import t2g_core as core

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
        ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


def handle(path, body):
    """Route dispatcher: returns (status, dict)."""
    if path == "/api/meta":
        return 200, {"stations": core.STATIONS,
                     "vehicles": list(core.VEHICLES.values()),
                     "destinations": core.DESTINATIONS,
                     "spot_prices": core.SPOT_PRICES}

    if path == "/api/optimize":
        return 200, core.optimize(
            vehicle_id=body.get("vehicle", "id4"),
            soc_pct=float(body.get("soc", 40)),
            target_pct=float(body.get("target", 80)),
            dest_id=body.get("destination", "d2"),
            window_h=int(body.get("window", 10)),
            v2g_on=bool(body.get("v2g", True)),
            start_hour=int(body.get("start_hour", 18)),
            deg_on=bool(body.get("deg", False)),
            eco=bool(body.get("eco", False)))

    if path == "/api/session/start":
        opt = core.optimize(
            vehicle_id=body.get("vehicle", "id4"),
            soc_pct=float(body.get("soc", 40)),
            target_pct=float(body.get("target", 80)),
            dest_id=body.get("destination", "d2"),
            window_h=int(body.get("window", 10)),
            v2g_on=bool(body.get("v2g", True)),
            start_hour=int(body.get("start_hour", 18)),
            eco=bool(body.get("eco", False)))
        if not opt["recommendation"]:
            return 400, {"error": "no reachable station"}
        return 200, core.start_session(opt, soc_pct=float(body.get("soc", 40)))

    if path == "/api/session/step":
        return 200, core.step_session(body.get("session_id", ""))

    if path == "/api/valuestack":
        return 200, core.value_stack(
            fleet_size=int(body.get("fleet", 500)),
            v2g_share_pct=float(body.get("v2g_share", 40)),
            kwh_per_vehicle_day=float(body.get("kwh_day", 15)))

    if path == "/api/grid":
        return 200, core.grid_profile(
            fleet_size=int(body.get("fleet", 1000)),
            v2g_share_pct=float(body.get("v2g_share", 40)),
            kwh_per_vehicle_day=float(body.get("kwh_day", 15)))

    if path == "/api/live":
        return 200, core.live()

    if path == "/api/countries":
        return 200, {"countries": core.COUNTRIES,
                     "co2": core.CO2_INTENSITY, "spot": core.SPOT_PRICES}

    if path == "/api/break_even":
        return 200, core.break_even(
            charger=body.get("charger", "DC50"),
            utilization_pct=float(body.get("utilization", 8)),
            margin_ct=float(body.get("margin", 12)),
            lang=body.get("lang", "fr"))

    if path == "/api/site":
        return 200, core.orchestrate_site(
            vehicles=body.get("vehicles", []),
            cap_kw=float(body.get("cap_kw", 22)),
            window_h=int(body.get("window_h", 8)))

    if path == "/api/site_optimal":
        return 200, core.site_optimal(
            vehicles=body.get("vehicles", []),
            cap_kw=float(body.get("cap_kw", 60)),
            eco=bool(body.get("eco", False)),
            v2g_enabled=bool(body.get("v2g_enabled", True)),
            window_h=int(body.get("window_h", 24)))

    if path == "/api/data_sources":
        return 200, core.SOURCES

    if path == "/api/sessions":
        return 200, core.list_sessions()

    if path == "/api/trip":
        return 200, core.plan_trip(
            vehicle_id=body.get("vehicle", "id4"),
            soc_pct=float(body.get("soc", 45)),
            origin_id=body.get("origin", "d1"),
            dest_id=body.get("destination", "d2"),
            target_pct=float(body.get("target", 80)))

    return 404, {"error": "unknown endpoint"}


class Handler(BaseHTTPRequestHandler):

    def _reply(self, code, payload, ctype="application/json"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            code, payload = handle(path, {})
            self._reply(code, payload)
            return
        if path in ("/", "/index.html"):
            fp = os.path.join(STATIC_DIR, "index.html")
            with open(fp, "rb") as f:
                self._reply(200, f.read(), "text/html; charset=utf-8")
            return
        # other static assets, path-sanitised
        safe = os.path.normpath(path.lstrip("/")).replace("..", "")
        fp = os.path.join(STATIC_DIR, safe)
        if os.path.isfile(fp):
            ext = os.path.splitext(fp)[1]
            with open(fp, "rb") as f:
                self._reply(200, f.read(), MIME.get(ext, "application/octet-stream"))
            return
        self._reply(404, {"error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode() or "{}")
            code, payload = handle(self.path.split("?")[0], body)
            self._reply(code, payload)
        except Exception as exc:  # keep the demo alive no matter what
            self._reply(500, {"error": str(exc)})

    def log_message(self, fmt, *args):  # quieter default logging
        print(f"{self.address_string()} {fmt % args}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"VoltHub T2G platform (stdlib server) -> http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
