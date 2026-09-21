"""
data_loader.py — charge les données réelles depuis le dossier data/.
Aucune donnée n est plus codée en dur dans le moteur.
Si un fichier manque, une erreur explicite est levée (les fichiers sont générés
par scripts/fetch_data.py et versionnés dans data/).
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"data/{name} introuvable — lancez scripts/fetch_data.py pour (re)générer les données")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all():
    """Charge et normalise toutes les données externes du prototype."""
    prices = _load("prix_spot.json")
    co2 = _load("co2_intensite.json")
    bornes = _load("bornes.json")
    veh = _load("vehicules.json")
    dest = _load("destinations.json")
    hyp = _load("hypotheses.json")
    ev_share = _load("ev_part_pays.json")
    soleil = _load("soleil.json")
    details = _load("pays_details.json")

    stations = bornes["stations"]
    marge = hyp["bornes"]["marge_defaut_eur_par_kwh"]
    frais = hyp["bornes"]["frais_session_defaut"]
    for st in stations:
        st.setdefault("markup", marge)
        st.setdefault("fee", frais)

    # fusion : parts de marché réelles (Our World in Data) + détails éditoriaux
    detail_by_fr = {d["country"]["fr"]: d for d in details}
    countries = []
    for c in ev_share["countries"]:
        fr = c["country"]["fr"]
        d = detail_by_fr.get(fr)
        if not d:
            continue
        countries.append({
            "country": {"fr": fr, "en": c["country"]["en"]},
            "share": c["share"], "share_year": c["year"],
            "share_source": c["source"],
            "v2g": d["v2g"], "actors": d["actors"], "policy": d["policy"],
        })
    countries.sort(key=lambda c: -c["share"])

    sources = {
        "prix": prices["source"], "co2": co2["source"], "solaire": soleil["source"], "bornes": bornes["source"],
        "vehicules": veh["source"], "destinations": dest["source"],
        "hypotheses": hyp["source"], "part_marche": ev_share["source"],
        "fetched_at": prices.get("fetched_at"),
    }
    return {
        "spot_prices": prices["spot_prices"],
        "solaire_pct": soleil["solaire_pct"],
        "co2_intensite": co2["co2_intensite"],
        "stations": stations,
        "vehicules": veh["vehicules"],
        "destinations": dest["destinations"],
        "hypotheses": hyp,
        "countries": countries,
        "sources": sources,
    }
