"""
VoltHub T2G — core simulation engine
Transportation-to-Grid platform prototype.

Implements:
  - Smart-charging optimizer (location / time / duration / cost estimation)
  - V2G (bidirectional) planning: discharge at peak, recharge at valley
  - Live charging session state machine
  - Value stacking across the 4 Guidehouse T2G business models
  - Grid load orchestration analytics (dumb vs smart vs V2G)
"""
import math
import uuid

# ---------------------------------------------------------------------------
# Static reference data (simulated city, 20 x 20 km)
# ---------------------------------------------------------------------------

# Hourly spot-like electricity price curve (EUR/kWh) — typical day-ahead shape
SPOT_PRICES = [
    0.14, 0.12, 0.10, 0.10, 0.11, 0.13,          # 00-05 night valley
    0.18, 0.24, 0.27, 0.25, 0.20, 0.17,          # 06-11 morning ramp/peak
    0.15, 0.15, 0.16, 0.18, 0.22, 0.32,          # 12-17 afternoon ramp
    0.38, 0.36, 0.28, 0.22, 0.17, 0.15,          # 18-23 evening peak
]

STATIONS = [
    {"id": "st1",  "name": "VoltHub Central Mall",   "x": 5.0,  "y": 6.0,  "type": "DC",  "kw": 150, "v2g": False, "markup": 0.19, "fee": 1.50, "slots": 6},
    {"id": "st2",  "name": "GreenPark Hub",          "x": 12.0, "y": 4.0,  "type": "DC",  "kw": 50,  "v2g": False, "markup": 0.14, "fee": 0.80, "slots": 4},
    {"id": "st3",  "name": "Riverside V2G Station",  "x": 15.0, "y": 12.0, "type": "HPC", "kw": 22,  "v2g": True,  "markup": 0.10, "fee": 0.50, "slots": 8},
    {"id": "st4",  "name": "Business District Garage", "x": 8.0, "y": 13.0, "type": "AC",  "kw": 22,  "v2g": True,  "markup": 0.09, "fee": 0.00, "slots": 12},
    {"id": "st5",  "name": "Northgate Supercharger", "x": 4.0,  "y": 16.0, "type": "DC",  "kw": 150, "v2g": False, "markup": 0.22, "fee": 2.00, "slots": 8},
    {"id": "st6",  "name": "University Campus AC",   "x": 10.0, "y": 17.0, "type": "AC",  "kw": 7,   "v2g": True,  "markup": 0.07, "fee": 0.00, "slots": 20},
    {"id": "st7",  "name": "OldTown Bidirectional",  "x": 9.0,  "y": 8.5,  "type": "HPC", "kw": 11,  "v2g": True,  "markup": 0.11, "fee": 0.30, "slots": 5},
    {"id": "st8",  "name": "Airport Long-Stay",      "x": 18.0, "y": 6.0,  "type": "AC",  "kw": 22,  "v2g": True,  "markup": 0.08, "fee": 0.00, "slots": 15},
]

# Grid carbon intensity (gCO2/kWh) — correlated with the price curve:
# night/midday = baseload + renewables (clean), evening peak = gas peakers (dirty)
CO2_INTENSITY = [
    45, 40, 38, 38, 42, 55,          # 00-05 night baseload
    90, 140, 180, 150, 120, 100,     # 06-11 morning ramp
    80, 70, 75, 90, 130, 190,        # 12-15 solar dip
    380, 420, 350, 240, 160, 90,     # 16-23 evening peakers
]

# Battery degradation cost of V2G cycling (EUR per kWh exported) —
# published studies range 0.05–0.12 €/kWh; we use a mid estimate
DEG_RATE = 0.07

VEHICLES = {
    "zoe":     {"id": "zoe",     "name": "Renault Zoe R135",     "battery": 52, "max_kw": 46,  "cons": 0.17, "v2g": False},
    "leaf":    {"id": "leaf",    "name": "Nissan Leaf e+",       "battery": 62, "max_kw": 50,  "cons": 0.17, "v2g": True},
    "id4":     {"id": "id4",     "name": "VW ID.4 Pro",          "battery": 77, "max_kw": 125, "cons": 0.19, "v2g": True},
    "model3":  {"id": "model3",  "name": "Tesla Model 3 LR",     "battery": 75, "max_kw": 250, "cons": 0.16, "v2g": False},
    "kangoo":  {"id": "kangoo",  "name": "Renault Kangoo E-Tech (fleet)", "battery": 45, "max_kw": 80, "cons": 0.21, "v2g": True},
    "ebus":    {"id": "ebus",    "name": "City e-Bus (HD fleet)", "battery": 300, "max_kw": 150, "cons": 1.10, "v2g": True},
}

DESTINATIONS = [
    {"id": "d1", "name": "Home — Suburbs",        "x": 3.5,  "y": 3.5},
    {"id": "d2", "name": "Office — Business District", "x": 8.0, "y": 13.0},
    {"id": "d3", "name": "Shopping Mall",         "x": 5.0,  "y": 6.0},
    {"id": "d4", "name": "University Campus",     "x": 10.0, "y": 17.0},
    {"id": "d5", "name": "Airport T2",            "x": 18.5, "y": 5.5},
    {"id": "d6", "name": "Convention Center",     "x": 14.5, "y": 11.5},
]

# Charging taper: available power falls off as the battery fills up
def _taper(soc):
    """Power multiplier at a given state of charge (0..1)."""
    if soc < 0.55:
        return 1.0
    if soc >= 1.0:
        return 0.0
    return max(0.15, 1.0 - 0.75 * (soc - 0.55) / 0.45)

def sim_charge_hours(start_kwh, end_kwh, battery, station_kw, vehicle_kw):
    """Simulate charging, return duration in hours and energy delivered."""
    p = min(station_kw, vehicle_kw)
    t, kwh, dt = 0.0, start_kwh, 1.0 / 60.0
    while kwh < end_kwh and t < 24.0:
        kwh += p * _taper(kwh / battery) * dt
        t += dt
    return t, kwh - start_kwh


# ---------------------------------------------------------------------------
# Optimizer — "estimation des lieux, temps, durée et coût de recharge"
# ---------------------------------------------------------------------------

def _cheapest_hours(h_start, n_hours, kwh_per_hour, energy_needed, markup):
    """Smart (V1G) scheduling: pick the cheapest hours inside the parking window."""
    hours = [(SPOT_PRICES[(h_start + i) % 24] + markup, (h_start + i) % 24)
             for i in range(n_hours)]
    hours.sort()
    plan = {h: 0.0 for _, h in hours}
    remaining = energy_needed
    for price, h in hours:
        if remaining <= 0:
            break
        take = min(kwh_per_hour, remaining)
        plan[h] += take
        remaining -= take
    return plan, remaining


def _v2g_plan(h_start, n_hours, kwh_per_hour, energy_needed, markup,
              battery, soc_start_kwh, reserve_frac, efficiency):
    """Bidirectional plan: discharge during the most expensive hours, recharge during the cheapest."""
    hours = [(SPOT_PRICES[(h_start + i) % 24] + markup, (h_start + i) % 24)
             for i in range(n_hours)]
    ranked_desc = sorted(hours, reverse=True)

    # Energy we may export: everything above the reserve, minus the energy still
    # needed to reach the target at the end of the window.
    exportable = max(0.0, soc_start_kwh - reserve_frac * battery - energy_needed)

    discharge = {h: 0.0 for _, h in hours}
    exported = 0.0
    revenue = 0.0
    for price, h in ranked_desc:
        if exportable - exported <= 0.01:
            break
        take = min(kwh_per_hour, exportable - exported)
        discharge[h] = take
        exported += take
        revenue += take * price * efficiency  # round-trip losses paid by the driver

    # Recharge what we exported plus the original need, in the cheapest hours
    total_to_buy = energy_needed + exported / efficiency
    plan = {h: 0.0 for _, h in hours}
    remaining = total_to_buy
    for price, h in sorted(hours):
        if remaining <= 0:
            break
        take = min(kwh_per_hour, remaining)
        plan[h] += take
        remaining -= take

    return plan, discharge, exported, revenue, remaining


def optimize(vehicle_id, soc_pct, target_pct, dest_id, window_h, v2g_on, start_hour,
             deg_on=False):
    veh = VEHICLES[vehicle_id]
    dest = next(d for d in DESTINATIONS if d["id"] == dest_id)
    soc = max(0.0, min(1.0, soc_pct / 100.0))
    target = max(soc, min(1.0, target_pct / 100.0))
    window_h = max(1, min(24, int(window_h)))
    results = []

    for st in STATIONS:
        dist = math.hypot(dest["x"] - st["x"], dest["y"] - st["y"])
        energy_to_reach = dist * veh["cons"]
        soc_on_arrival = soc - energy_to_reach / veh["battery"]
        if soc_on_arrival < 0.05:
            continue  # unreachable with the current charge

        kwh_needed = max(0.0, (target - soc_on_arrival) * veh["battery"])
        can_v2g = v2g_on and st["v2g"] and veh["v2g"]
        charge_kw = min(st["kw"], veh["max_kw"])
        kwh_per_hour = charge_kw  # simplified: 1h slots at nominal power

        if can_v2g:
            plan, discharge, exported, v2g_revenue, shortfall = _v2g_plan(
                start_hour, window_h, kwh_per_hour, kwh_needed, st["markup"],
                veh["battery"], soc_on_arrival * veh["battery"], 0.30, 0.92)
            if shortfall > 0:  # window too short for charge + export — fall back to V1G
                plan, _ = _cheapest_hours(
                    start_hour, window_h, kwh_per_hour, kwh_needed, st["markup"])
                discharge, exported, v2g_revenue = {h: 0.0 for h in plan}, 0.0, 0.0
                can_v2g = False
        else:
            plan, _ = _cheapest_hours(
                start_hour, window_h, kwh_per_hour, kwh_needed, st["markup"])
            discharge, exported, v2g_revenue = {h: 0.0 for h in plan}, 0.0, 0.0

        # --- Load-orchestrator power modulation --------------------------------
        # Same cost, lower peak power: instead of blasting the cheapest hours
        # at full power, spread the energy equally over those hours.
        modulated = False
        p_mod = charge_kw
        if kwh_needed > 0 and sum(discharge.values()) == 0:
            used_hours = [h for h, e in plan.items() if e > 0]
            if len(used_hours) > 1:
                p_mod = sum(plan.values()) / len(used_hours)
                if p_mod < charge_kw * 0.95:
                    plan = {h: (p_mod if h in used_hours else 0.0) for h in plan}
                    modulated = True

        buy_cost = sum(e * (SPOT_PRICES[h] + st["markup"]) for h, e in plan.items())
        end_kwh = soc_on_arrival * veh["battery"] + sum(plan.values()) - exported
        if modulated:
            duration, _ = sim_charge_hours(soc_on_arrival * veh["battery"],
                                           min(end_kwh, veh["battery"]),
                                           veh["battery"], p_mod, p_mod)
        else:
            duration, _ = sim_charge_hours(soc_on_arrival * veh["battery"],
                                           min(end_kwh, veh["battery"]),
                                           veh["battery"], st["kw"], veh["max_kw"])
        # CO2 footprint: purchased energy minus avoided peaker emissions from
        # V2G discharge (can be net-negative = the car cleans up the grid)
        co2_g = sum(e * CO2_INTENSITY[h] for h, e in plan.items())
        co2_avoided = sum(e * CO2_INTENSITY[h] for h, e in discharge.items())
        co2_g -= co2_avoided
        dumb_co2 = kwh_needed * CO2_INTENSITY[start_hour]
        if dumb_co2 > 0:
            co2_saved_pct = 100 * (dumb_co2 - co2_g) / dumb_co2
        elif co2_avoided > 0:
            co2_saved_pct = 100.0  # no charging needed, pure V2G service
        else:
            co2_saved_pct = 0.0
        co2_saved_pct = max(0.0, min(100.0, co2_saved_pct))
        # battery wear of V2G cycling
        deg_cost = exported * DEG_RATE if (can_v2g and deg_on) else 0.0
        total_cost = buy_cost - v2g_revenue + st["fee"] + deg_cost
        dumb_cost = kwh_needed * (SPOT_PRICES[start_hour] + st["markup"]) + st["fee"]
        score = total_cost + 0.15 * duration  # time penalty 0.15 €/h

        timeline = [{"h": (start_hour + i) % 24,
                     "price": SPOT_PRICES[(start_hour + i) % 24],
                     "charge_kw": plan.get((start_hour + i) % 24, 0.0),
                     "discharge_kw": discharge.get((start_hour + i) % 24, 0.0)}
                    for i in range(window_h)]

        results.append({
            "station": st, "distance_km": round(dist, 1),
            "duration_h": round(duration, 2),
            "kwh_bought": round(sum(plan.values()), 1),
            "kwh_sold": round(exported, 1),
            "energy_cost": round(buy_cost, 2), "fee": st["fee"],
            "v2g_revenue": round(v2g_revenue, 2),
            "degradation_cost": round(deg_cost, 2),
            "co2_g": round(co2_g),
            "co2_saved_pct": round(co2_saved_pct, 1),
            "net_cost": round(total_cost, 2),
            "dumb_cost": round(dumb_cost, 2),
            "saving_pct": round(100 * (dumb_cost - total_cost) / dumb_cost, 1) if dumb_cost > 0 else 0,
            "score": round(score, 2),
            "timeline": timeline,
            "v2g": can_v2g,
            "modulated": modulated,
            "peak_kw": round(max(plan.values()), 1) if kwh_needed > 0 else 0.0,
            "nominal_kw": charge_kw,
        })

    results.sort(key=lambda r: r["score"])
    return {
        "vehicle": veh, "destination": dest,
        "start_hour": start_hour, "window_h": window_h,
        "recommendation": results[0] if results else None,
        "options": results,
    }


# ---------------------------------------------------------------------------
# Live session simulator (10-minute ticks)
# ---------------------------------------------------------------------------

SESSIONS = {}

def start_session(opt_result, soc_pct=40.0):
    """Create a live session from an optimizer result (uses the recommendation)."""
    sid = str(uuid.uuid4())[:8]
    rec = opt_result["recommendation"]
    SESSIONS[sid] = {
        "station": rec["station"], "vehicle": opt_result["vehicle"],
        "timeline": rec["timeline"], "idx": 0, "tick": 0,
        "soc_pct": float(soc_pct), "spent": 0.0, "earned": 0.0, "energy_bought": 0.0,
        "energy_sold": 0.0, "done": False, "log": [],
    }
    return {"session_id": sid, "station": rec["station"], "vehicle": opt_result["vehicle"]}


def _session_state(s):
    last = s["log"][-1] if s["log"] else {"kw": 0.0, "mode": "idle", "price": 0.0}
    return {"soc_pct": round(s["soc_pct"], 1), "spent": round(s["spent"], 2),
            "earned": round(s["earned"], 2), "energy_bought": round(s["energy_bought"], 2),
            "energy_sold": round(s["energy_sold"], 2),
            "mode": last["mode"], "power_kw": round(last["kw"], 2),
            "price": round(last["price"], 3),
            "progress": round(100 * (s["idx"] + s["tick"] / 6.0) / max(1, len(s["timeline"])), 1),
            "hour": s["timeline"][min(s["idx"], len(s["timeline"]) - 1)]["h"] if s["timeline"] else 0,
            "log": s["log"][-40:]}


def step_session(sid):
    s = SESSIONS.get(sid)
    if not s:
        return {"error": "unknown session"}
    if s["done"]:
        return {"done": True, **_session_state(s)}

    h = s["timeline"][s["idx"]]
    price = h["price"] + s["station"]["markup"]
    dt = 10 / 60.0  # hours per tick
    if h["discharge_kw"] > 0:
        e = h["discharge_kw"] * dt
        s["soc_pct"] = max(5.0, s["soc_pct"] - 100 * e / s["vehicle"]["battery"])
        s["earned"] += e * price * 0.92
        s["energy_sold"] += e
        mode, kw = "v2g_discharge", h["discharge_kw"]
    elif h["charge_kw"] > 0:
        kw = h["charge_kw"] * _taper(s["soc_pct"] / 100.0)
        e = kw * dt
        s["soc_pct"] = min(100.0, s["soc_pct"] + 100 * e / s["vehicle"]["battery"])
        s["spent"] += e * price
        s["energy_bought"] += e
        mode = "charging"
    else:
        mode, kw = "idle", 0.0

    s["log"].append({"t": round(s["idx"] + s["tick"] / 6.0, 2), "soc": round(s["soc_pct"], 1),
                     "kw": round(kw, 2), "mode": mode, "price": price})
    s["tick"] += 1
    if s["tick"] >= 6:
        s["tick"] = 0
        s["idx"] += 1
        if s["idx"] >= len(s["timeline"]):
            s["done"] = True
    return {"done": False, **_session_state(s)}


# ---------------------------------------------------------------------------
# Value stacking — the 4 Guidehouse T2G business models
# ---------------------------------------------------------------------------

def value_stack(fleet_size, v2g_share_pct, kwh_per_vehicle_day=15.0):
    v2g_vehicles = fleet_size * v2g_share_pct / 100.0
    total_kwh_day = fleet_size * kwh_per_vehicle_day

    # 4.2 Charging Service Provider — margin on energy sold + session fees
    csp = total_kwh_day * 0.08 * 365 + fleet_size * 0.5 * 365

    # 4.1 Infrastructure Developer — utilisation fee collected per kWh
    infra = total_kwh_day * 0.02 * 365

    # 4.3 Load Orchestrator — V2G arbitrage + frequency-regulation capacity payments
    arbitrage = v2g_vehicles * 10.0 * 0.20 * 0.92 * 365 * 0.85     # 10 kWh cycled/day
    capacity = v2g_vehicles * 7.0 * 15.0                            # 7 kW enrolled @ 15 €/kW-yr
    orchestrator = arbitrage + capacity

    # 4.4 Mobility Provider — MaaS subscription on the fleet
    maas = fleet_size * 0.35 * 12 * 0.30 * 12                       # 35% attach, 30% margin

    models = [
        {"model": "Infrastructure Developer", "revenue": round(infra),
         "detail": "2 c€/kWh utilisation fee on charging points"},
        {"model": "Charging Service Provider", "revenue": round(csp),
         "detail": "8 c€/kWh energy margin + session fees"},
        {"model": "Load Orchestrator", "revenue": round(orchestrator),
         "detail": "V2G arbitrage (20 c€/kWh spread) + 15 €/kW-yr capacity"},
        {"model": "Mobility Provider (MaaS)", "revenue": round(maas),
         "detail": "12 €/mo subscription, 30% margin, 35% attach rate"},
    ]
    total = sum(m["revenue"] for m in models)
    return {"fleet_size": fleet_size, "v2g_vehicles": round(v2g_vehicles),
            "models": models, "total": round(total),
            "per_vehicle_year": round(total / max(1, fleet_size)),
            "stacking_bonus_pct": round(100 * (total - csp) / max(1, csp))}


# ---------------------------------------------------------------------------
# Grid orchestration analytics — dumb vs smart vs V2G load profiles
# ---------------------------------------------------------------------------

def grid_profile(fleet_size, v2g_share_pct, kwh_per_vehicle_day=15.0):
    dumb = [0.0] * 24
    smart = [0.0] * 24
    e = kwh_per_vehicle_day
    p_max = 11.0  # home/work AC power per vehicle

    # --- Dumb charging: plug in and charge at full power immediately ---
    # 70% arrive at 18:00 (evening peak), 30% at 08:00 (morning peak)
    n_evening = fleet_size * 0.70
    n_morning = fleet_size * 0.30
    dumb[18] += n_evening * p_max                       # full power hour 1
    dumb[19] += n_evening * max(0.0, (e - p_max)) / 1.0  # remainder of the session
    dumb[8] += n_morning * p_max
    dumb[9] += n_morning * max(0.0, (e - p_max)) / 1.0

    # --- Smart orchestration: same energy, spread over the night valley 01-07 ---
    valley_hours = 7
    base_kw_per_veh = e / valley_hours
    for h in range(1, 1 + valley_hours):
        smart[h] += fleet_size * base_kw_per_veh

    # V2G fleet discharges into the evening peak 18-20 (negative load),
    # then recharges the exported energy inside the valley.
    v2g_n = fleet_size * v2g_share_pct / 100.0
    for h in range(18, 21):
        smart[h] -= v2g_n * 3.3          # ~3.3 kW discharge per vehicle
    recharge_kw = v2g_n * 3.3 * 3 / valley_hours
    for h in range(1, 1 + valley_hours):
        smart[h] += recharge_kw

    peak_dumb = max(dumb)
    peak_smart = max(smart)
    return {"hours": list(range(24)), "dumb_kw": [round(x, 1) for x in dumb],
            "smart_kw": [round(x, 1) for x in smart],
            "spot": SPOT_PRICES,
            "kpi": {
                "peak_dumb_kw": round(peak_dumb, 1),
                "peak_smart_kw": round(peak_smart, 1),
                "peak_reduction_pct": round(100 * (peak_dumb - peak_smart) / peak_dumb, 1),
                "v2g_discharge_kw": round(v2g_n * 3.3, 1),
            }}


# ---------------------------------------------------------------------------
# Charging-station economics — CAPEX / OPEX / break-even
# ---------------------------------------------------------------------------

CHARGER_TYPES = {
    "AC7":   {"kw": 7,   "capex": 3500,   "opex": 300,
              "label": {"fr": "CA 7 kW — domicile / copropriété", "en": "AC 7 kW — home / apartment block"}},
    "AC22":  {"kw": 22,  "capex": 9000,   "opex": 500,
              "label": {"fr": "CA 22 kW — parking / entreprise", "en": "AC 22 kW — car park / business"}},
    "DC50":  {"kw": 50,  "capex": 45000,  "opex": 3000,
              "label": {"fr": "DC 50 kW — urbain", "en": "DC 50 kW — urban"}},
    "DC150": {"kw": 150, "capex": 95000,  "opex": 5500,
              "label": {"fr": "DC 150 kW — autoroute", "en": "DC 150 kW — highway"}},
}


def break_even(charger="DC50", utilization_pct=8.0, margin_ct=12.0):
    """Return the economics of one charging point.
    CAPEX = hardware + installation + grid connection; OPEX = maintenance + rent.
    Revenue = energy dispensed x margin."""
    ct = CHARGER_TYPES.get(charger, CHARGER_TYPES["DC50"])
    kwh_year = ct["kw"] * 8760 * max(0.0, min(100.0, utilization_pct)) / 100.0
    revenue = kwh_year * margin_ct / 100.0
    profit = revenue - ct["opex"]
    payback = round(ct["capex"] / profit, 1) if profit > 0 else None
    return {
        "charger": charger, "label": ct["label"],
        "kw": ct["kw"], "capex": ct["capex"], "opex": ct["opex"],
        "utilization_pct": utilization_pct, "margin_ct": margin_ct,
        "kwh_year": round(kwh_year), "revenue_year": round(revenue),
        "profit_year": round(profit), "payback_years": payback,
    }


# ---------------------------------------------------------------------------
# Retours d'expérience — country comparison (illustrative figures, 2023-2024)
# ---------------------------------------------------------------------------

COUNTRIES = [
    {"share": 90,
     "country": {"fr": "Norvège", "en": "Norway"},
     "v2g": {"fr": "Projets pilotes (Nuvve, Fermata) ; réseau déjà très flexible (hydro)",
             "en": "Pilot projects (Nuvve, Fermata); grid already very flexible (hydro)"},
     "actors": {"fr": "Zaptec, Fortum Charge & Drive, Easee", "en": "Zaptec, Fortum Charge & Drive, Easee"},
     "policy": {"fr": "Exonérations fiscales totales, péages et parking gratuits pour les VE",
                "en": "Full tax exemptions, free tolls and parking for EVs"}},
    {"share": 42,
     "country": {"fr": "Pays-Bas", "en": "Netherlands"},
     "v2g": {"fr": "Leader de l'orchestration : Jedlix ↔ TenneT, pilotes V2G à grande échelle",
             "en": "Orchestration leader: Jedlix ↔ TenneT, large-scale V2G pilots"},
     "actors": {"fr": "Jedlix, Elaad, Shell Recharge (ex-NewMotion)", "en": "Jedlix, Elaad, Shell Recharge (ex-NewMotion)"},
     "policy": {"fr": "Congestion du réseau = forte rémunération de la flexibilité",
                "en": "Grid congestion = high remuneration of flexibility"}},
    {"share": 26,
     "country": {"fr": "France", "en": "France"},
     "v2g": {"fr": "Elli Flex / Mobilize pilots ; réseau nucléaire = CO2 déjà bas",
             "en": "Elli Flex / Mobilize pilots; nuclear grid = already low CO2"},
     "actors": {"fr": "Electra, Renault Mobilize, Freshmile, Ionity", "en": "Electra, Renault Mobilize, Freshmile, Ionity"},
     "policy": {"fr": "Bonus écologique, Le décret bornes, éco-PTZ",
                "en": "Purchase bonus, charging-point decree, eco-loan"}},
    {"share": 24,
     "country": {"fr": "Allemagne", "en": "Germany"},
     "v2g": {"fr": "Pionnier ISO 15118-20 (Plug & Charge + bidirectionnel) ; loi Solarpaket 2024",
             "en": "ISO 15118-20 pioneer (Plug & Charge + bidirectional); Solarpaket law 2024"},
     "actors": {"fr": "Elli (VW), EnBW, Plugsurfing, Sonnet", "en": "Elli (VW), EnBW, Plugsurfing, Sonnet"},
     "policy": {"fr": "Subventions KfW, dynamique solaire + batteries domestiques",
                "en": "KfW subsidies, home solar + battery dynamics"}},
    {"share": 25,
     "country": {"fr": "États-Unis (Californie)", "en": "United States (California)"},
     "v2g": {"fr": "Bus scolaires V2G (Nuvve) ; FERC 2222 ouvre les marchés DER",
             "en": "V2G school buses (Nuvve); FERC 2222 opens DER markets"},
     "actors": {"fr": "Tesla Supercharger, EVgo, ChargePoint, Fermata", "en": "Tesla Supercharger, EVgo, ChargePoint, Fermata"},
     "policy": {"fr": "Crédits d'impôt IRA, mandats ZEV de l'État",
                "en": "IRA tax credits, state ZEV mandates"}},
    {"share": 37,
     "country": {"fr": "Chine", "en": "China"},
     "v2g": {"fr": "Pilotes V2G à Shanghai ; échange de batteries (NIO) comme alternative",
             "en": "V2G pilots in Shanghai; battery swapping (NIO) as an alternative"},
     "actors": {"fr": "NIO, BYD, TELD (plus grand réseau mondial)", "en": "NIO, BYD, TELD (largest network worldwide)"},
     "policy": {"fr": "Crédits NEV, déploiement DC massif soutenu par l'État",
                "en": "NEV credits, state-backed massive DC rollout"}},
]


def live():
    """Snapshot for the live ticker + station occupancy (changes on every call)."""
    import random
    import datetime
    h = datetime.datetime.now().hour
    busy = 0.55 if 8 <= h <= 20 else 0.20
    stations = []
    for st in STATIONS:
        occ = int(round(st["slots"] * min(0.95, busy * random.uniform(0.6, 1.2))))
        stations.append({"id": st["id"], "occupied": occ, "free": max(0, st["slots"] - occ),
                         "slots": st["slots"]})
    return {"hour": h, "price": SPOT_PRICES[h], "co2": CO2_INTENSITY[h], "stations": stations}


# ---------------------------------------------------------------------------
# Trip planner — "do I need a charging stop on the way?"
# ---------------------------------------------------------------------------

def plan_trip(vehicle_id, soc_pct, origin_id, dest_id, target_pct=80.0):
    """Check a trip origin -> destination: direct or with a charging stop.
    Arrival reserve: 10% of battery."""
    veh = VEHICLES[vehicle_id]
    o = next((x for x in DESTINATIONS if x["id"] == origin_id), DESTINATIONS[0])
    d = next((x for x in DESTINATIONS if x["id"] == dest_id), DESTINATIONS[0])
    batt, cons = veh["battery"], veh["cons"]
    soc = max(0.0, min(1.0, soc_pct / 100.0))
    target = max(soc, min(1.0, target_pct / 100.0))

    dist = math.hypot(d["x"] - o["x"], d["y"] - o["y"])
    e_trip = dist * cons
    arrival = soc - e_trip / batt

    res = {"vehicle": veh["name"], "origin": o["name"], "destination": d["name"],
           "distance_km": round(dist, 1), "energy_kwh": round(e_trip, 1),
           "direct": arrival >= 0.10,
           "arrival_soc_pct": round(100 * arrival, 1), "stops": []}

    if res["direct"]:
        res["found"] = True
        return res

    # need a stop: evaluate every station as a potential charging stop
    avg_spot = sum(SPOT_PRICES) / 24.0
    stops = []
    for st in STATIONS:
        d1 = math.hypot(st["x"] - o["x"], st["y"] - o["y"])
        d2 = math.hypot(d["x"] - st["x"], d["y"] - st["y"])
        soc_stop = soc - d1 * cons / batt
        if soc_stop < 0.10:                    # cannot even reach the station
            continue
        arrival_final = target - d2 * cons / batt
        if arrival_final < 0.10:               # would not reach destination after stop
            continue
        kwh = (target - soc_stop) * batt
        duration, _ = sim_charge_hours(soc_stop * batt, target * batt,
                                       batt, st["kw"], veh["max_kw"])
        stops.append({
            "station": st["name"], "detour_km": round(d1 + d2 - dist, 1),
            "charge_kwh": round(kwh, 1), "duration_h": round(duration, 2),
            "cost": round(kwh * (avg_spot + st["markup"]) + st["fee"], 2),
            "v2g": st["v2g"],
        })
    stops.sort(key=lambda s: (s["detour_km"], s["cost"]))
    res["stops"] = stops[:3]
    res["found"] = bool(res["stops"])
    return res


# ---------------------------------------------------------------------------
# Session registry — vehicles currently connected to the platform
# ---------------------------------------------------------------------------

def list_sessions():
    out = []
    for sid, s in SESSIONS.items():
        last = s["log"][-1] if s["log"] else {"mode": "idle"}
        out.append({
            "id": sid, "vehicle": s["vehicle"]["name"], "station": s["station"]["name"],
            "mode": last["mode"], "soc_pct": round(s["soc_pct"], 1),
            "progress": round(100 * (s["idx"] + s["tick"] / 6.0) / max(1, len(s["timeline"])), 1),
            "done": s["done"],
            "spent": round(s["spent"], 2), "earned": round(s["earned"], 2),
        })
    return {"count": len(out), "sessions": out}
