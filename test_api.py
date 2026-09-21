#!/usr/bin/env python3
"""VoltHub T2G — API smoke tests.
Usage:  python3 test_api.py            (expects server on localhost:5000)
        python3 test_api.py myhost:port
"""
import json
import sys
import urllib.request

BASE = f"http://{sys.argv[1] if len(sys.argv) > 1 else 'localhost:5000'}"
passed, failed = 0, 0


def call(path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method=method or ("POST" if body is not None else "GET"))
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


print("== 1. Static page ==")
with urllib.request.urlopen(BASE + "/", timeout=10) as r:
    html = r.read().decode()
check("GET / returns 200 + dashboard", "VoltHub" in html and "tab-plan" in html)

print("== 2. Metadata ==")
meta = call("/api/meta")
check("stations reelles chargees (>= 8)", len(meta["stations"]) >= 8)
check("6 vehicles", len(meta["vehicles"]) == 6)
check("6 destinations", len(meta["destinations"]) == 6)
check("24h price curve", len(meta["spot_prices"]) == 24 and min(meta["spot_prices"]) > 0)

print("== 3. Optimizer (V1G smart charging) ==")
opt = call("/api/optimize", {"vehicle": "id4", "soc": 45, "target": 80,
                             "destination": "d2", "window": 10,
                             "v2g": True, "start_hour": 17})
rec = opt.get("recommendation")
check("recommendation exists", rec is not None)
check("stations ranked by score",
      all(opt["options"][i]["score"] <= opt["options"][i + 1]["score"]
          for i in range(len(opt["options"]) - 1)))
check("smart plan cheaper than dumb charging", rec["net_cost"] < rec["dumb_cost"],
      f"net={rec['net_cost']} dumb={rec['dumb_cost']}")
check("saving_pct consistent",
      abs(rec["saving_pct"] - 100 * (rec["dumb_cost"] - rec["net_cost"]) / rec["dumb_cost"]) < 0.2)
check("timeline covers window", len(rec["timeline"]) == 10)

print("== 4. Optimizer (V2G arbitrage) ==")
opt2 = call("/api/optimize", {"vehicle": "id4", "soc": 80, "target": 80,
                              "destination": "d2", "window": 10,
                              "v2g": True, "start_hour": 14})
rec2 = opt2["recommendation"]
check("V2G energy exported", rec2["kwh_sold"] > 0, f"sold={rec2['kwh_sold']}")
check("V2G revenue earned", rec2["v2g_revenue"] > 0)
check("net cost negative (driver earns)", rec2["net_cost"] < 0, f"net={rec2['net_cost']}")
check("reserve respected (>=30% = 23.1 kWh of 77 kWh)",
      rec2["kwh_sold"] <= 0.80 * 77 - 0.30 * 77 + 1e-6)

print("== 5. Optimizer edge cases ==")
opt3 = call("/api/optimize", {"vehicle": "zoe", "soc": 10, "target": 80,
                              "destination": "d5", "window": 4,
                              "v2g": False, "start_hour": 18})
check("unreachable trip handled (no crash)", isinstance(opt3.get("options"), list))
opt4 = call("/api/optimize", {"vehicle": "leaf", "soc": 45, "target": 80,
                              "destination": "d2", "window": 6,
                              "v2g": False, "start_hour": 18})
check("non-V2G vehicle => no export", opt4["recommendation"]["kwh_sold"] == 0)

print("== 6. Live session ==")
sess = call("/api/session/start", {"vehicle": "leaf", "soc": 70, "target": 80,
                                   "destination": "d2", "window": 12,
                                   "v2g": True, "start_hour": 16})
sid = sess["session_id"]
check("session created", len(sid) == 8)
modes = set()
for _ in range(80):
    st = call("/api/session/step", {"session_id": sid})
    modes.add(st["mode"])
    if st.get("done"):
        break
check("session completes", st.get("done") is True)
check("all 3 modes observed (charge/discharge/idle)",
      {"charging", "v2g_discharge", "idle"} <= modes, str(modes))
check("SoC stayed within battery limits", 0 <= st["soc_pct"] <= 100)
check("money flows both ways", st["spent"] > 0 and st["earned"] > 0,
      f"spent={st['spent']} earned={st['earned']}")
check("unknown session rejected", "error" in call("/api/session/step", {"session_id": "nope"}))

print("== 7. Value stacking ==")
vs = call("/api/valuestack", {"fleet": 500, "v2g_share": 40, "kwh_day": 15})
check("4 business models", len(vs["models"]) == 4)
check("total = sum of models", vs["total"] == sum(m["revenue"] for m in vs["models"]))
check("per-vehicle revenue consistent",
      vs["per_vehicle_year"] == round(vs["total"] / 500))
vs0 = call("/api/valuestack", {"fleet": 500, "v2g_share": 0, "kwh_day": 15})
check("stacking bonus grows with V2G share", vs["total"] > vs0["total"])

print("== 8. Grid analytics ==")
g = call("/api/grid", {"fleet": 1000, "v2g_share": 40})
check("24h profiles", len(g["dumb_kw"]) == 24 and len(g["smart_kw"]) == 24)
check("peak reduction between 0 and 100%",
      0 < g["kpi"]["peak_reduction_pct"] < 100, str(g["kpi"]))
check("V2G creates negative load (discharge)",
      min(g["smart_kw"]) < 0 <= min(g["dumb_kw"]))


print("== 9. Live snapshot, CO2 & degradation, break-even, countries ==")
lv = call("/api/live")
check("live: price/co2 consistent with hour", lv["price"] == meta["spot_prices"][lv["hour"]])
check("live: occupancy within slot limits",
      all(0 <= o["free"] <= o["slots"] for o in lv["stations"]))
lv2 = call("/api/live")
check("live: occupancy changes between calls (alive)",
      any(a["free"] != b["free"] for a, b in zip(lv["stations"], lv2["stations"])))

optd = call("/api/optimize", {"vehicle": "id4", "soc": 80, "target": 80,
                              "destination": "d2", "window": 10,
                              "v2g": True, "start_hour": 14, "deg": True})
rd = optd["recommendation"]
check("degradation cost computed when enabled", rd["degradation_cost"] > 0)
check("V2G-only session: net-negative CO2 (avoids peakers)", rd["co2_g"] < 0)
check("V2G-only session: full CO2 saving flagged", rd["co2_saved_pct"] == 100)
optv1g = call("/api/optimize", {"vehicle": "id4", "soc": 45, "target": 80,
                                 "destination": "d2", "window": 10,
                                 "v2g": False, "start_hour": 17})
rv = optv1g["recommendation"]
check("V1G: CO2 footprint positive", rv["co2_g"] > 0)
check("V1G: smart charging cuts CO2", rv["co2_saved_pct"] > 0, str(rv["co2_saved_pct"]))

be = call("/api/break_even", {"charger": "DC150", "utilization": 10, "margin": 15})
check("break-even: profitable at 10% utilization", be["profit_year"] > 0)
check("break-even: payback in 3-15 years",
      be["payback_years"] is not None and 3 < be["payback_years"] < 15, str(be["payback_years"]))
be0 = call("/api/break_even", {"charger": "DC150", "utilization": 1, "margin": 2})
check("break-even: never pays back at 1% utilization", be0["payback_years"] is None)

src = call("/api/data_sources")
check("sources de donnees renseignees", bool(src.get("prix")) and bool(src.get("bornes")))

cs = call("/api/countries")["countries"]
check("6 countries returned", len(cs) == 6)
check("country shares plausible", all(0 < c["share"] <= 100 for c in cs))


print("== 10. Session registry, power modulation, trip planner ==")
s1 = call("/api/session/start", {"vehicle": "leaf", "soc": 70, "target": 80,
                                 "destination": "d2", "window": 12, "v2g": True, "start_hour": 16})
s2 = call("/api/session/start", {"vehicle": "model3", "soc": 60, "target": 80,
                                 "destination": "d3", "window": 12, "v2g": False, "start_hour": 16})
reg = call("/api/sessions")
check("session registry lists both sessions", reg["count"] >= 2)
check("registry entries have vehicle + station + mode",
      all(s.get("vehicle") and s.get("station") and s.get("mode") for s in reg["sessions"]))

optm = call("/api/optimize", {"vehicle": "id4", "soc": 45, "target": 80,
                              "destination": "d2", "window": 10,
                              "v2g": False, "start_hour": 12})
rm = optm["recommendation"]
check("power modulated when window allows", rm["modulated"] is True)
check("modulated peak below nominal", rm["peak_kw"] < rm["nominal_kw"],
      f"peak={rm['peak_kw']} nominal={rm['nominal_kw']}")
check("modulation preserves total energy (plan = bought)",
      abs(rm["kwh_bought"] - sum(t["charge_kw"] for t in rm["timeline"])) < 0.15,
      str(rm["kwh_bought"]))
check("plan timeline reflects modulated power",
      max(t["charge_kw"] for t in rm["timeline"]) <= rm["peak_kw"] + 0.06)

tr = call("/api/trip", {"vehicle": "zoe", "soc": 12, "origin": "d1",
                        "destination": "d6", "target": 80})
check("low-SoC trip flagged as needing a stop", tr["direct"] is False)
check("viable stop proposed", tr["found"] is True and len(tr["stops"]) >= 1)
check("stop is reachable and reaches destination",
      tr["stops"][0]["detour_km"] >= 0 and tr["stops"][0]["charge_kwh"] > 0)
trd = call("/api/trip", {"vehicle": "zoe", "soc": 90, "origin": "d1",
                         "destination": "d2", "target": 80})
check("high-SoC trip is direct", trd["direct"] is True and trd["stops"] == [])


print("== 11. Orchestrateur multi-VE (site) + mode éco solaire ==")
site = call("/api/site", {
    "vehicles": [
        {"name": "VE-A", "battery": 60, "soc": 20, "target": 80, "departure_h": 3},
        {"name": "VE-B", "battery": 75, "soc": 40, "target": 80, "departure_h": 6},
        {"name": "VE-C", "battery": 52, "soc": 55, "target": 80, "departure_h": 8},
        {"name": "VE-D", "battery": 77, "soc": 30, "target": 80, "departure_h": 10}],
    "cap_kw": 22, "window_h": 10})
check("site: pic <= cap", site["site_peak_kw"] <= 22.0, str(site["site_peak_kw"]))
check("site: au moins 3/4 servis", site["served"] >= 3, str(site["served"]))
check("site: priorité au départ le plus tôt",
      site["vehicles"][0]["delivered_kwh"] > 0 and
      sum(site["vehicles"][0]["schedule"][3:]) == 0,
      str(site["vehicles"][0]["schedule"]))
check("site: cohérence livré/curbe",
      abs(sum(site["site_curve"]) - sum(v["delivered_kwh"] for v in site["vehicles"])) < 0.5)

e = call("/api/optimize", {"vehicle": "id4", "soc": 45, "target": 80,
                           "destination": "d2", "window": 12, "v2g": False,
                           "start_hour": 8, "eco": True})
check("mode éco : plan généré", e["recommendation"] is not None and
      e["recommendation"]["kwh_bought"] > 0)

print(f"\nRESULT: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
