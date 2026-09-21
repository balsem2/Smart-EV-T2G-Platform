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
import data_loader

_DATA = data_loader.load_all()

SPOT_PRICES = _DATA["spot_prices"]
CO2_INTENSITY = _DATA["co2_intensite"]
SOLAR = _DATA["solaire_pct"]
STATIONS = _DATA["stations"]
VEHICLES = {v["id"]: v for v in _DATA["vehicules"]}
DESTINATIONS = _DATA["destinations"]
COUNTRIES = _DATA["countries"]
SOURCES = _DATA["sources"]

_HYP = _DATA["hypotheses"]
DEG_RATE = _HYP["v2g"]["usure_eur_par_kwh"]
V2G_RESERVE = _HYP["v2g"]["reserve_soc"]
V2G_EFFICACITE = _HYP["v2g"]["efficacite_aller_retour"]
MARGE_DEFAUT = _HYP["bornes"]["marge_defaut_eur_par_kwh"]
CHARGER_TYPES = _HYP["charger_types"]
TRIP = _HYP["trajet"]
ECO_CFG = _HYP["eco"]
SITE_CFG = _HYP["site"]
BUSINESS = _HYP["business"]
GRID = _HYP["reseau"]
CHARGE = _HYP["charge"]
OCCUPATION = _HYP["occupation"]

def _taper(soc):
    """Power multiplier at a given state of charge (0..1)."""
    if soc < CHARGE["seuil_taper"]:
        return 1.0
    if soc >= 1.0:
        return 0.0
    span = 1.0 - CHARGE["seuil_taper"]
    return max(CHARGE["puissance_min_relative"],
               1.0 - CHARGE["pente_taper"] * (soc - CHARGE["seuil_taper"]) / span)

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

def _cheapest_hours(h_start, n_hours, kwh_per_hour, energy_needed, markup,
                    eco=False, start_hour=None):
    """Smart (V1G) scheduling: pick the cheapest hours inside the parking window.
    En mode éco, les heures solaires reçoivent un bonus (prix effectif réduit)."""
    bonus = {}
    if eco and start_hour is not None:
        for i in range(n_hours):
            h = (h_start + i) % 24
            bonus[h] = (SOLAR[h] / 100.0) * ECO_CFG["bonus_solaire_eur_par_kwh_max"]
    hours = [(SPOT_PRICES[(h_start + i) % 24] + markup - bonus.get((h_start + i) % 24, 0.0),
              (h_start + i) % 24)
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
              battery, soc_start_kwh, reserve_frac, efficiency, eco=False):
    """Bidirectional plan: discharge during the most expensive hours, recharge during the cheapest."""
    hours = [(SPOT_PRICES[(h_start + i) % 24] + markup, (h_start + i) % 24)
             for i in range(n_hours)]
    ranked_desc = sorted(hours, reverse=True)  # decharge : heures les plus cheres

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
    plan, _short = _cheapest_hours(h_start, n_hours, kwh_per_hour, total_to_buy,
                                   markup, eco=eco, start_hour=h_start)

    return plan, discharge, exported, revenue, _short

def optimize(vehicle_id, soc_pct, target_pct, dest_id, window_h, v2g_on, start_hour,
             deg_on=False, eco=False):
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
                veh["battery"], soc_on_arrival * veh["battery"], V2G_RESERVE, V2G_EFFICACITE)
            if shortfall > 0:  # window too short for charge + export — fall back to V1G
                plan, _ = _cheapest_hours(
                    start_hour, window_h, kwh_per_hour, kwh_needed, st["markup"],
                    eco=eco, start_hour=start_hour)
                discharge, exported, v2g_revenue = {h: 0.0 for h in plan}, 0.0, 0.0
                can_v2g = False
        else:
            plan, _ = _cheapest_hours(
                start_hour, window_h, kwh_per_hour, kwh_needed, st["markup"],
                eco=eco, start_hour=start_hour)
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

def value_stack(fleet_size, v2g_share_pct, kwh_per_vehicle_day=None):
    B = BUSINESS
    kwh_per_vehicle_day = kwh_per_vehicle_day or B["kwh_par_vehicule_jour"]
    v2g_vehicles = fleet_size * v2g_share_pct / 100.0
    total_kwh_day = fleet_size * kwh_per_vehicle_day

    # 4.2 Charging Service Provider — margin on energy sold + session fees
    csp = total_kwh_day * B["marge_csp_eur_par_kwh"] * 365 + \
          fleet_size * B["frais_session_annuel_par_vehicule"]

    # 4.1 Infrastructure Developer — utilisation fee collected per kWh
    infra = total_kwh_day * B["frais_infrastructure_eur_par_kwh"] * 365

    # 4.3 Load Orchestrator — V2G arbitrage + frequency-regulation capacity payments
    arbitrage = (v2g_vehicles * B["kwh_cycle_v2g_par_jour"] * B["spread_v2g_eur_par_kwh"]
                 * B["efficacite_v2g"] * 365 * B["utilisation_v2g"])
    capacity = v2g_vehicles * B["kw_inscrits_par_vehicule"] * B["paiement_capacite_eur_par_kw_an"]
    orchestrator = arbitrage + capacity

    # 4.4 Mobility Provider — MaaS subscription on the fleet
    maas = (fleet_size * B["attach_maaS"] * 12 * B["marge_maaS"]
            * B["abonnement_maaS_eur_mois"])

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
    G = GRID
    dumb = [0.0] * 24
    smart = [0.0] * 24
    e = kwh_per_vehicle_day
    p_max = G["p_charge_domicile_kw"]

    # --- Dumb charging: plug in and charge at full power immediately ---
    n_evening = fleet_size * G["part_soir"]
    n_morning = fleet_size * G["part_matin"]
    dumb[18] += n_evening * p_max                       # full power hour 1
    dumb[19] += n_evening * max(0.0, (e - p_max)) / 1.0  # remainder of the session
    dumb[8] += n_morning * p_max
    dumb[9] += n_morning * max(0.0, (e - p_max)) / 1.0

    # --- Smart orchestration: same energy, spread over the night valley 01-07 ---
    valley_hours = G["heures_vallee"]
    base_kw_per_veh = e / valley_hours
    for h in range(1, 1 + valley_hours):
        smart[h] += fleet_size * base_kw_per_veh

    # V2G fleet discharges into the evening peak 18-20 (negative load),
    # then recharges the exported energy inside the valley.
    v2g_n = fleet_size * v2g_share_pct / 100.0
    p_dis = G["p_decharge_v2g_kw"]
    for h in range(18, 21):
        smart[h] -= v2g_n * p_dis        # discharge per vehicle (V2G)
    recharge_kw = v2g_n * p_dis * 3 / valley_hours
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
                "v2g_discharge_kw": round(v2g_n * GRID["p_decharge_v2g_kw"], 1),
            }}

# ---------------------------------------------------------------------------
# Charging-station economics — CAPEX / OPEX / break-even
# ---------------------------------------------------------------------------

def break_even(charger="DC50", utilization_pct=8.0, margin_ct=12.0, lang="fr"):
    """Return the economics of one charging point.
    CAPEX = hardware + installation + grid connection; OPEX = maintenance + rent.
    Revenue = energy dispensed x margin."""
    ct = CHARGER_TYPES.get(charger, CHARGER_TYPES["DC50"])
    kwh_year = ct["kw"] * 8760 * max(0.0, min(100.0, utilization_pct)) / 100.0
    revenue = kwh_year * margin_ct / 100.0
    profit = revenue - ct["opex"]
    payback = round(ct["capex"] / profit, 1) if profit > 0 else None
    label = ct["label"][lang] if isinstance(ct["label"], dict) else ct["label"]
    return {
        "charger": charger, "label": label,
        "kw": ct["kw"], "capex": ct["capex"], "opex": ct["opex"],
        "utilization_pct": utilization_pct, "margin_ct": margin_ct,
        "kwh_year": round(kwh_year), "revenue_year": round(revenue),
        "profit_year": round(profit), "payback_years": payback,
    }

# ---------------------------------------------------------------------------
# Retours d'expérience — comparaison par pays (parts réelles Our World in Data)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Occupation des bornes — état évolutif (arrivées / départs de véhicules)
# ---------------------------------------------------------------------------

_OCC = {"ratio": {}, "last": {}}


def _tick_occupancy(hour):
    """Fait évoluer l'occupation des bornes à chaque appel (arrivées/départs).

    Chaque borne suit une marche aléatoire rappelée vers le régime jour/nuit et
    plafonnée. Si un tick ne change aucune valeur (petites capacités + arrondi),
    un mouvement est forcé : l'état reste vivant par construction.
    """
    import random
    in_day = OCCUPATION["heures_jour_debut"] <= hour < OCCUPATION["heures_jour_fin"]
    target = OCCUPATION["taux_jour"] if in_day else OCCUPATION["taux_nuit"]
    var = OCCUPATION["variation_par_appel"]
    rappel = OCCUPATION["rappel_vers_regime"]
    cap = OCCUPATION["plafond"]

    for st in STATIONS:
        r = _OCC["ratio"].get(st["id"], target)
        r += random.uniform(-var, var) + (target - r) * rappel
        _OCC["ratio"][st["id"]] = max(0.0, min(cap, r))

    snap = {st["id"]: int(round(st["slots"] * _OCC["ratio"][st["id"]])) for st in STATIONS}
    if snap == _OCC["last"]:
        for st in random.sample(STATIONS, len(STATIONS)):
            cur, slots = snap[st["id"]], st["slots"]
            if cur < slots:                       # une voiture arrive
                snap[st["id"]] = cur + 1
                _OCC["ratio"][st["id"]] = (cur + 1) / slots
                break
            if cur > 0:                           # une voiture part
                snap[st["id"]] = cur - 1
                _OCC["ratio"][st["id"]] = (cur - 1) / slots
                break
    _OCC["last"] = snap
    return snap


def live():
    """Snapshot for the live ticker + station occupancy (evolves on every call)."""
    import datetime
    h = datetime.datetime.now().hour
    occ = _tick_occupancy(h)
    stations = [{"id": st["id"], "occupied": occ[st["id"]], "free": st["slots"] - occ[st["id"]],
                 "slots": st["slots"]} for st in STATIONS]
    return {"hour": h, "price": SPOT_PRICES[h], "co2": CO2_INTENSITY[h], "solar": SOLAR[h], "stations": stations}

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
           "direct": arrival >= TRIP["reserve_arrivee"],
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
        if soc_stop < TRIP["reserve_arrivee"]:  # cannot even reach the station
            continue
        arrival_final = target - d2 * cons / batt
        if arrival_final < TRIP["reserve_arrivee"]:  # would not reach destination after stop
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
# Orchestrateur multi-VE sur un site — répartition d une puissance limitée
# (le scénario : N véhicules partagent une connexion de puissance cap_kw)
# ---------------------------------------------------------------------------

NOMINAL_PAR_VE = SITE_CFG["nominal_par_ve_kw"]  # lu depuis data/hypotheses.json

def orchestrate_site(vehicles, cap_kw, window_h):
    """Répartit une puissance limitée (cap_kw) entre plusieurs véhicules.

    vehicles : [{"name", "battery", "soc"(%), "target"(%), "departure_h"(heures
    après le début de la fenêtre)}]. Algorithme : à chaque heure, les véhicules
    actifs reçoivent une puissance proportionnelle à leur urgence
    (besoin restant / heures restantes), plafonnée au cap du site et à leur
    puissance nominale. Retour : courbe de charge du site + résultat par véhicule.
    """
    cap_kw = max(1.0, float(cap_kw))
    window_h = max(1, min(24, int(window_h)))
    state = []
    for i, v in enumerate(vehicles):
        batt = max(1.0, float(v.get("battery", 60)))
        soc = max(0.0, min(100.0, float(v.get("soc", 40))))
        target = max(soc, min(100.0, float(v.get("target", 80))))
        state.append({
            "name": v.get("name", f"VE {i + 1}"),
            "battery": batt,
            "soc0_pct": round(soc, 1),
            "soc_kwh": batt * soc / 100.0,
            "target_kwh": batt * target / 100.0,
            "need_kwh": round(max(0.0, batt * (target - soc) / 100.0), 1),
            "dep": max(1, min(window_h, int(v.get("departure_h", window_h)))),
            "delivered": 0.0,
            "schedule": [0.0] * window_h,
        })

    site_curve = [0.0] * window_h
    for h in range(window_h):
        active = [v for v in state if v["dep"] > h and v["soc_kwh"] < v["target_kwh"]]
        if not active:
            continue
        demands, urgencies = [], []
        for v in active:
            need = v["target_kwh"] - v["soc_kwh"]
            ideal = min(need, NOMINAL_PAR_VE)
            urgency = need / max(1.0, v["dep"] - h)
            demands.append((v, ideal, urgency))
            urgencies.append(urgency)
        total = sum(d[1] for d in demands)
        if total <= cap_kw:
            allocations = [(v, ideal) for v, ideal, _ in demands]
        else:
            urg_total = sum(urgencies)
            allocations = [(v, min(ideal, cap_kw * urg / urg_total))
                           for v, ideal, urg in demands]
        hour_total = 0.0
        for v, alloc in allocations:
            v["soc_kwh"] += alloc
            v["delivered"] += alloc
            v["schedule"][h] = round(alloc, 2)
            hour_total += alloc
        site_curve[h] = round(hour_total, 2)

    results = []
    served = 0
    for v in state:
        met = v["soc_kwh"] >= v["target_kwh"] - 0.01
        served += 1 if met else 0
        results.append({
            "name": v["name"], "soc0_pct": v["soc0_pct"],
            "soc_final_pct": round(100 * v["soc_kwh"] / v["battery"], 1),
            "need_kwh": v["need_kwh"], "delivered_kwh": round(v["delivered"], 1),
            "departure_h": v["dep"], "target_met": met,
            "schedule": v["schedule"],
        })
    return {
        "cap_kw": cap_kw, "window_h": window_h,
        "site_curve": site_curve, "site_peak_kw": round(max(site_curve), 2) if site_curve else 0.0,
        "vehicles": results, "served": served, "total": len(results),
    }

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


# ---------------------------------------------------------------------------
# Orchestrateur de flotte — planification 24 h sous plafond de site
# (utilise la vraie courbe de prix data/prix_spot.json + solaire RTE)
# ---------------------------------------------------------------------------

def site_optimal(vehicles, cap_kw, eco=False, v2g_enabled=True, window_h=24, start_hour=None):
    """Optimiseur de flotte : planifie la recharge et la décharge V2G de N véhicules
    sur la vraie courbe de prix, sous un plafond de puissance de site.

    vehicles : [{"veh_id" (id dans data/vehicules.json), "soc" (%), "target" (%),
                 "departure_h" (heures avant le départ)}]
    Retour : plannings par véhicule, courbe du site, coûts/revenus, KPIs.
    """
    import datetime as _dt
    h0 = int(start_hour) if start_hour is not None else _dt.datetime.now(_dt.timezone.utc).hour
    window_h = max(2, min(48, int(window_h)))
    cap_kw = max(1.0, float(cap_kw))
    RES, EFF = V2G_RESERVE, V2G_EFFICACITE
    eco_bonus = ECO_CFG["bonus_solaire_eur_par_kwh_max"] if eco else 0.0

    hours = list(range(window_h))
    price = [SPOT_PRICES[(h0 + h) % 24] for h in hours]
    solar = [SOLAR[(h0 + h) % 24] for h in hours]
    eff_price = [round(p - (s / 100.0) * eco_bonus, 4) for p, s in zip(price, solar)]

    state = []
    for i, v in enumerate(vehicles):
        spec = VEHICLES.get(v.get("veh_id"), list(VEHICLES.values())[0])
        batt = max(1.0, float(spec["battery"]))
        soc = min(100.0, max(0.0, float(v.get("soc", 40))))
        target = min(100.0, max(soc, float(v.get("target", 80))))
        dep = max(1, min(window_h, int(v.get("departure_h", window_h))))
        v2g_ok = v2g_enabled and bool(spec.get("v2g", False))
        state.append({
            "idx": i, "name": spec["name"], "veh_id": v.get("veh_id"),
            "battery": batt, "nominal": min(float(spec["max_kw"]), 50.0),
            "soc0_pct": round(soc * 100, 1), "soc_kwh": batt * soc / 100.0,
            "target_kwh": batt * target / 100.0,
            "need_kwh": round(max(0.0, batt * (target - soc) / 100.0), 1),
            "dep": dep, "v2g_ok": v2g_ok,
            "sched_c": [0.0] * window_h, "sched_d": [0.0] * window_h,
        })

    # --- Phase 1 : V2G — décharge aux heures les plus chères avant le départ ---
    for v in state:
        if not v["v2g_ok"]:
            continue
        # garde physique : export limité par la réserve ET par la capacité de
        # recharge restante (le véhicule doit finir à sa cible avant le départ)
        exportable = min(v["soc_kwh"] - RES * v["battery"],
                         (v["battery"] - v["soc_kwh"]) * EFF) - v["need_kwh"]
        if exportable <= 0:
            continue
        p_dis = min(11.0, v["nominal"])
        rem = exportable
        for h in sorted(range(v["dep"]), key=lambda hh: -price[hh]):
            if rem <= 0:
                break
            take = min(p_dis, rem)
            v["sched_d"][h] += take
            v["soc_kwh"] -= take
            rem -= take

    # --- Phase 2 : recharge — heures les moins chères (prix effectif), plafond de site ---
    remaining = [v["need_kwh"] + sum(v["sched_d"]) / EFF for v in state]
    for v, r in zip(state, remaining):
        r = r  # Remaining est manipulé via la liste ci-dessus
    for h in sorted(hours, key=lambda hh: eff_price[hh]):
        cap_left = cap_kw + sum(v["sched_d"][h] for v in state)  # la décharge libère du cap
        actives = [i for i, v in enumerate(state)
                   if h < v["dep"] and remaining[i] > 0.01]
        actives.sort(key=lambda i: -remaining[i])
        for i in actives:
            v = state[i]
            room = max(0.0, v["battery"] - v["soc_kwh"])
            alloc = min(v["nominal"], remaining[i], max(0.0, cap_left), room)
            if alloc <= 0:
                continue
            v["sched_c"][h] += round(alloc, 2)
            v["soc_kwh"] += alloc
            remaining[i] -= alloc
            cap_left -= alloc
            if cap_left <= 0:
                break

    # --- Résultats ---
    results, served = [], 0
    tot_cost = tot_rev = 0.0
    site_c = [round(sum(v["sched_c"][h] for v in state), 2) for h in hours]
    site_d = [round(sum(v["sched_d"][h] for v in state), 2) for h in hours]
    for v in state:
        charged = sum(v["sched_c"])
        exported = sum(v["sched_d"])
        cost = sum(v["sched_c"][h] * (price[h]) for h in hours)
        rev = sum(v["sched_d"][h] * (price[h]) * EFF for h in hours)
        met = remaining[v["idx"]] <= 0.01
        served += 1 if met else 0
        tot_cost += cost
        tot_rev += rev
        results.append({
            "name": v["name"], "veh_id": v["veh_id"], "soc0_pct": v["soc0_pct"],
            "soc_final_pct": round(100 * min(v["battery"], v["soc_kwh"]) / v["battery"], 1),
            "need_kwh": v["need_kwh"], "charged_kwh": round(charged, 1),
            "departure_h": v["dep"], "target_met": met,
            "exported_kwh": round(exported, 1), "v2g_revenue": round(rev, 2),
            "cost": round(cost, 2), "net": round(cost - rev, 2),
            "sched_c": v["sched_c"], "sched_d": v["sched_d"],
        })
    peak_net = round(max(site_c[h] - site_d[h] for h in hours), 2)
    return {
        "cap_kw": cap_kw, "window_h": window_h, "start_hour": h0,
        "prices": price, "eff_prices": eff_price, "solar": solar,
        "vehicles": results, "served": served, "total": len(results),
        "site_charge": site_c, "site_discharge": site_d,
        "peak_charge_kw": round(max(site_c), 2) if site_c else 0.0,
        "peak_net_kw": peak_net,
        "total_cost": round(tot_cost, 2), "total_v2g_revenue": round(tot_rev, 2),
        "net_cost": round(tot_cost - tot_rev, 2),
        "source": SOURCES["prix"],
    }
