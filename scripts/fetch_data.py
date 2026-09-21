#!/usr/bin/env python3
"""
fetch_data.py — met à jour les données réelles du dossier data/ (100 % gratuit, sans clé).

Sources :
  - Prix spot FR        : Fraunhofer Energy-Charts (api.energy-charts.info)  — CC BY 4.0
  - CO2 + solaire (FR)  : RTE eco2mix (opendata.reseaux-energies.fr)           — données ouvertes
  - Bornes réelles      : OpenStreetMap / Overpass API (POST)                     — ODbL
  - Part de VE par pays : Our World in Data (electric-car-sales-share)            — CC BY

Usage :
  python3 scripts/fetch_data.py            # tout mettre à jour
  python3 scripts/fetch_data.py --prices   # seulement les prix
  python3 scripts/fetch_data.py --co2 --solar --stations --shares
"""
import argparse
import collections
import datetime
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
NOW = datetime.datetime.now(datetime.timezone.utc)
UA = {"User-Agent": "VoltHubPrototype/1.0"}


def get(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def write(name, obj):
    with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"  OK -> data/{name}")


def fetch_prices():
    """Prix day-ahead FR (EUR/MWh -> EUR/kWh), moyenne par heure sur 7 jours."""
    start = int((NOW - datetime.timedelta(days=7)).timestamp())
    end = int(NOW.timestamp())
    d = json.loads(get(f"https://api.energy-charts.info/price?bzn=FR&start={start}&end={end}"))
    by_hour = collections.defaultdict(list)
    for ts, p in zip(d["unix_seconds"], d["price"]):
        if p is None:
            continue
        by_hour[datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).hour].append(p / 1000.0)
    curve = [round(statistics.mean(by_hour[h]), 4) for h in range(24)]
    write("prix_spot.json", {
        "source": "Fraunhofer Energy-Charts (api.energy-charts.info) — prix day-ahead FR, CC BY 4.0",
        "fetched_at": NOW.isoformat(), "unit": "EUR/kWh",
        "note": "moyenne par heure sur les 7 derniers jours (UTC)",
        "spot_prices": curve})


def fetch_co2():
    """Intensité CO2 nationale (g/kWh) — RTE eco2mix."""
    url = "https://opendata.reseaux-energies.fr/api/records/1.0/search/?" + urllib.parse.urlencode(
        {"dataset": "eco2mix-national-tr", "q": "", "rows": 500, "sort": "-date_heure"})
    d = json.loads(get(url))
    by_hour = collections.defaultdict(list)
    for rec in d["records"]:
        f = rec["fields"]
        co2 = next((v for k, v in f.items()
                    if "co2" in k.lower() and isinstance(v, (int, float)) and v > 0), None)
        if co2 is None:
            continue
        by_hour[int(f["date_heure"].split("T")[1].split(":")[0])].append(co2)
    curve = [round(statistics.mean(by_hour[h]), 1) if by_hour[h] else None for h in range(24)]
    if not any(curve):
        raise RuntimeError("aucune valeur CO2 recue")
    fill = statistics.mean(v for v in curve if v is not None)
    curve = [round(v if v is not None else fill, 1) for v in curve]
    write("co2_intensite.json", {
        "source": "RTE eco2mix (opendata.reseaux-energies.fr) — taux de CO2 national, donnees ouvertes",
        "fetched_at": NOW.isoformat(), "unit": "gCO2/kWh",
        "note": "moyenne par heure (UTC), dernieres 24-48 h",
        "co2_intensite": curve})


def fetch_solar():
    """Part solaire dans la production FR (%) — RTE eco2mix (solaire / consommation)."""
    url = "https://opendata.reseaux-energies.fr/api/records/1.0/search/?" + urllib.parse.urlencode(
        {"dataset": "eco2mix-national-tr", "q": "", "rows": 500, "sort": "-date_heure"})
    d = json.loads(get(url))
    by_hour = collections.defaultdict(list)
    for rec in d["records"]:
        f = rec["fields"]
        sol, conso = f.get("solaire"), f.get("consommation")
        if not isinstance(sol, (int, float)) or not isinstance(conso, (int, float)) or conso <= 0:
            continue
        by_hour[int(f["date_heure"].split("T")[1].split(":")[0])].append(100.0 * sol / conso)
    if not by_hour:
        raise RuntimeError("aucune valeur solaire recue")
    curve = [round(statistics.mean(by_hour[h]), 1) if by_hour[h] else 0.0 for h in range(24)]
    write("soleil.json", {
        "source": "RTE eco2mix (opendata.reseaux-energies.fr) — solaire/consommation, donnees ouvertes",
        "fetched_at": NOW.isoformat(), "unit": "% de la production",
        "note": "part solaire moyenne par heure (UTC)",
        "solaire_pct": curve})


CITIES = {
    # nom -> (lat centre, lon centre, bbox Overpass)
    "Paris": (48.853, 2.349, (48.83, 2.28, 48.89, 2.36)),
    "Lyon": (45.764, 4.836, (45.73, 4.79, 45.79, 4.89)),
    "Bordeaux": (44.838, -0.579, (44.81, -0.62, 44.87, -0.54)),
}


def fetch_stations(city="Paris"):
    """Bornes réelles OpenStreetMap (ville au choix) -> grille km 0-20."""
    cy, cx, bbox = CITIES[city]
    query = (f'[out:json][timeout:40];node["amenity"="charging_station"]'
             f'({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});out center 40;')
    d = json.loads(get("https://overpass-api.de/api/interpreter",
                       data=urllib.parse.urlencode({"data": query}).encode()))
    KX, KY = 73.1, 111.0
    stations, seen = [], set()
    for el in d["elements"]:
        tags = el.get("tags", {})
        # Naming fallback chain: name > operator/network (+street) > id.
        # Never produce an anonymous label like "Terminal inconnu" for the demo.
        name = (tags.get("name") or "").strip()
        if not name:
            op = (tags.get("operator") or tags.get("network") or "").strip()
            street = (tags.get("addr:street") or tags.get("addr:place") or "").strip()
            if op and street:
                name = f"{op} \u2013 {street}"
            elif op:
                name = f"Borne {op}"
            elif street:
                name = f"Borne {street}"
            else:
                name = f"Borne OSM {el['id']}"
        if name in seen:
            continue
        seen.add(name)
        x = max(1.0, min(19.0, 10 + (el["lon"] - cx) * KX))
        y = max(1.0, min(19.0, 10 + (el["lat"] - cy) * KY))
        kw = 22
        for k, v in tags.items():
            if ":output" in k and str(v).replace(".", "").isdigit():
                kw = max(kw, int(float(v)))
        stations.append({"id": "osm" + str(el["id"]), "name": name[:40],
                         "x": round(x, 2), "y": round(y, 2),
                         "type": "DC" if kw >= 43 else "AC", "kw": kw, "v2g": True,
                         "markup": 0.15, "fee": 0.0, "slots": max(1, int(tags.get("capacity", 2))),
                         "operator": tags.get("operator", ""), "osm_lat": el["lat"], "osm_lon": el["lon"]})
        if len(stations) >= 14:
            break
    write("bornes.json", {
        "source": f"OpenStreetMap / Overpass API — amenity=charging_station, {city} centre, ODbL",
        "fetched_at": NOW.isoformat(),
        "note": "puissance AC par defaut (hypothese) ; conversion lat/lon -> grille km 0-20",
        "stations": stations})


def fetch_shares():
    """Part de VE dans les ventes par pays — Our World in Data (CC BY)."""
    csv = get("https://ourworldindata.org/grapher/electric-car-sales-share.csv?csvType=full").decode()
    lines = csv.strip().splitlines()
    rows = collections.defaultdict(dict)
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 4 or not parts[2].isdigit():
            continue
        rows[parts[0]][int(parts[2])] = parts[3]
    sel = {"Norway": "Norvège", "Netherlands": "Pays-Bas", "France": "France",
           "Germany": "Allemagne", "United States": "États-Unis", "China": "Chine"}
    countries = []
    for en, fr in sel.items():
        years = rows.get(en, {})
        if not years:
            continue
        last = max(years)
        countries.append({"country": {"fr": fr, "en": en}, "share": float(years[last]),
                          "year": last, "source": "Our World in Data (IEA/EAFO), CC BY"})
    countries.sort(key=lambda c: -c["share"])
    write("ev_part_pays.json", {"source": "Our World in Data — electric-car-sales-share (CC BY)",
          "fetched_at": NOW.isoformat(), "countries": countries})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Met à jour les données réelles de data/")
    ap.add_argument("--prices", action="store_true")
    ap.add_argument("--co2", action="store_true")
    ap.add_argument("--solar", action="store_true")
    ap.add_argument("--stations", action="store_true")
    ap.add_argument("--shares", action="store_true")
    ap.add_argument("--city", default="Paris", choices=sorted(CITIES))
    args = ap.parse_args()
    jobs = []
    if not any(vars(args).values()):
        jobs = [fetch_prices, fetch_co2, fetch_solar, fetch_stations, fetch_shares]
    else:
        if args.prices: jobs.append(fetch_prices)
        if args.co2: jobs.append(fetch_co2)
        if args.solar: jobs.append(fetch_solar)
        if args.stations: jobs.append(lambda: fetch_stations(args.city))
        if args.shares: jobs.append(fetch_shares)
    print(f"Mise a jour des donnees ({NOW:%Y-%m-%d %H:%M} UTC) :")
    errors = 0
    for job in jobs:
        try:
            job()
        except Exception as e:
            errors += 1
            print(f"  ERREUR {job.__name__}: {e}")
    sys.exit(1 if errors else 0)
