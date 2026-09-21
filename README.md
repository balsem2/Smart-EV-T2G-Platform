# VoltHub T2G — Smart EV Charging / Transportation-to-Grid Platform Prototype

Prototype for **Proj5 — Smart EV charging ou Transport-to-Grid (T2G)**.

The platform runs on **real open data**: day-ahead market prices (Fraunhofer
Energy-Charts), French grid carbon intensity and solar generation (RTE éCO2mix),
real charging stations in Paris (OpenStreetMap) and real 2025 EV market shares
(Our World in Data). Every number on screen is traceable — `/api/data_sources`
lists source, licence and fetch date for each dataset.

It demonstrates, in one running demo, the four topics of the project:

| Project part | Where it is in the prototype |
|---|---|
| **1. Complexité de la charge mobile** | Tab 5 *Flotte mobile* — animated 60-EV fleet moving through the city (commute, evening activities, night charging, V2G discharge at the 18–21h peak) showing that the grid **never has full visibility of EV locations**. Also Tab 4 *Analyse réseau* — EV as **load / storage / power plant** (SAS–Intel *Charging Ahead with EV Analytics*). |
| **2. Plate-forme digitale (technique)** | The whole app: REST API backend (13 endpoints) + optimizer engine (estimation des **lieux, temps, durée et coût** de recharge) + live session telemetry + trip planner + **Smart Site** multi-vehicle orchestration. Tabs 1, 2 and 4b. |
| **3. Business model adopté dans le monde** | Tab 3 *Modèles & valeur* — the **4 business models of the Guidehouse T2G white paper** with annual revenue simulation and value-stacking bonus, a **break-even calculator** (CAPEX/OPEX/payback per charger type), **plus the « Qui fait quoi ? Qui paie ? Où acheter ? » table** (actors, payers, procurement channels). |
| **4. Retours d'expériences + démo** | Tab 6 *Retours d'expérience* — country comparison (Norway, Netherlands, France, Germany, US-California, China) using **real OWID 2025 EV shares** + V2G status, actors and policy; the VW/Elli, Shell/NewMotion, BP/Chargemaster, GM/Bechtel case studies in the Tab 3 note; the *Live Session* is your **live T2G demo**. |

The 7 tabs (UI labels in French): **1** Recharge intelligente (plan) · **2**
Session en direct · **3** Modèles & valeur · **4** Analyse réseau · **4b**
Smart site · **5** Flotte mobile · **6** Retours d'expérience.

**Alive-platform features:** live ticker in the header (real spot price + grid CO₂
+ solar share + hour, refreshed every 5 s), evolving station occupancy on the map
(vehicles arrive and leave — green/red rings, tooltips), CO₂ footprint and V2G
battery-degradation cost in every optimizer result, hover tooltips on the plan
chart and city map, **session registry** (all vehicles currently plugged into the
platform, Tab 2), **power modulation** (same cost, reduced peak power — the
orchestrator spreads energy over the cheapest hours instead of blasting them),
**eco mode** (prefer the hours when solar generation is high), **trip planner**
(« do I need a charging stop on the way? ») and **Smart Site** (several vehicles
sharing one limited site connection).

> The interface is in **French** (matching the project brief) with a full **EN**
> toggle; industry terms (V2G, SoC, Load Orchestrator…) stay in English as in the
> literature.

## Run it

```bash
cd t2g
python3 app.py
# open http://localhost:5000
```

**Zero dependencies** — pure Python 3 standard library (no Flask, no pip install,
no CDN). Runs on any machine with any Python 3, fully offline (the datasets are
committed in `data/`).

```bash
PORT=8000 python3 app.py        # change the port
python3 test_api.py             # 58 automated tests (API + engine + data)
python3 scripts/fetch_data.py   # refresh the real datasets (free, no API key)
open http://localhost:5000/#test  # built-in browser self-test (writes a report in the page title)
```

## Architecture

```
static/index.html  ──HTTP───►  Stdlib HTTP API (app.py)  ──►  t2g_core.py (engine)
   7-tab dashboard              /api/meta        /api/optimize      • optimizer (lieux/temps/durée/coût)
   canvas map & charts          /api/live        /api/trip          • V2G plan (discharge peak, charge valley)
   vanilla JS, offline          /api/sessions    /api/site          • power modulation + schedule
   FR / EN toggle               /api/session/start|step             • multi-vehicle Smart Site allocation
                                /api/valuestack  /api/break_even    • value stacking (4 business models)
                                /api/grid        /api/countries     • grid orchestration analytics
                                /api/data_sources                   • session registry + telemetry
data/  ──►  data_loader.py  ──►  (all numbers on screen come from here — nothing hardcoded)
  prix_spot.json (Fraunhofer) · co2_intensite.json + soleil.json (RTE)
  bornes.json (OpenStreetMap Paris) · vehicules.json · destinations.json
  ev_part_pays.json (Our World in Data 2025) · pays_details.json · hypotheses.json
```

## How the optimizer works (part 2 — "estimation")

For every station near the destination it computes:

1. **Lieu** — detour distance (km) and whether the current SoC can reach it.
2. **Temps / durée** — charging duration simulated minute-by-minute with a
   power-taper curve (power drops as the battery fills).
3. **Coût** — energy bought in the *cheapest hourly slots* of the parking
   window (day-ahead price curve + station markup + session fee), compared
   against "dumb" charging at the arrival hour → % saved.
4. **V2G bonus** — if the car and the station are bidirectional, the engine
   sells the energy above a 30% reserve during the *most expensive* hours and
   re-buys it in the cheapest ones → the net cost can go **negative** (the
   driver earns money).

## Value stacking (part 3)

`/api/valuestack` annualises, for a fleet:

- **Infrastructure Developer** — utilisation fee per kWh dispensed.
- **Charging Service Provider** — energy margin (8 c€/kWh) + session fees.
- **Load Orchestrator** — V2G arbitrage (20 c€/kWh spread, 0.92 efficiency)
  + frequency-regulation capacity payments (15 €/kW-year).
- **Mobility Provider (MaaS)** — subscription revenue share.

Stacking the four models yields ≈ +60% vs a charging-only model — this is the
"multisided value exchange" argument of the Guidehouse paper.

## Demo script (5 minutes, pour la soutenance)

1. **Tab 1** — pick *VW ID.4 Pro*, SoC 45%, destination *Business District*,
   arrival 17h, V2G ON → **Optimiser**. Show the ranking: the recommended station
   charges in cheap slots (≈60% cheaper than dumb charging).
2. **Tab 1** — raise SoC to 80%, Optimize again → the plan now *discharges at
   the evening peak*: **net cost is negative**. That is T2G.
3. Click **Démarrer la session en direct** → **Tab 2** — auto-play: the car charges when
   the price is low and *sells back* at 18–20h. Point at the energy-flow
   animation and the telemetry log (this is your live T2G demo).
4. **Tab 5 Flotte mobile** — press **Lancer la journée**: watch 60 EVs move
   home → work → evening → home; pause at 18h30 to show the V2G virtual power
   plant and the "invisibles pour le réseau" KPI.
5. **Tab 3** — 500 vehicles, 40% V2G → ≈ €500k/year, +60% stacking bonus.
   Walk the « Qui fait quoi ? Qui paie ? Où acheter ? » table.
6. **Tab 4** — 1000 vehicles: dumb charging creates a 7.7 MW evening peak;
   orchestration + V2G cuts it by ≈65%. This is what the *Load Orchestrator*
   sells to the grid operator.

## Real-world actors to quote (part 4)

- **Volkswagen / Elli** — OEM-owned charging & energy brand (CSP model).
- **Nuvve, Fermata Energy** — commercial V2G platforms (Load Orchestrator).
- **TenneT & Jedlix** — smart-charging orchestration with drivers in NL/BE.
- **Ionity, Fastned, ChargePoint** — Infrastructure Developers.
- **UBL / MaaS players (Whim)** — Mobility Provider integration.

## Limitations (say this in the Q&A!)

- **Real data for prices, CO₂, solar, stations and EV shares** (Fraunhofer, RTE,
  OpenStreetMap, Our World in Data — see `/api/data_sources`). Still **simulated
  states**: station occupancy, the 60-EV fleet behaviour and the business
  assumptions (`data/hypotheses.json`, calibrated on published ranges).
- One-shot hourly optimisation (no rolling MPC, no network constraints).
- No OCPP/ISO 15118 yet — the roadmap to a "real" platform is:
  **OCPP 2.0.1** (charger↔platform), **ISO 15118-20** (Plug&Charge + bidirectional
  power transfer), **OCPI** (roaming between operators), **MQTT/Kafka** for telemetry,
  real day-ahead prices (ENTSO-E) and a scheduling optimizer (linear programming).
