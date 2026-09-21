# Smart EV - Transportation-to-Grid Platform

Academic full-stack prototype that compares normal EV charging, smart V1G charging,
and simulated V2G operation using electricity price, grid load, solar generation,
and wind generation.

## Architecture

```text
React dashboard
      |
      v
FastAPI REST API
      |
      +-- SQLAlchemy ORM --> PostgreSQL 18
      |
      +-- Smart charging optimizer
              |
              +-- Austrian energy profile
```

## Implemented workflow

1. Register or log in to a personal account.
2. Complete the mandatory first-login onboarding by selecting an EV from the
   controlled dataset catalogue.
3. Select one of the preloaded Austrian charging stations.
4. Submit current SoC, target SoC, and departure time.
5. Compare normal, V1G, and V2G strategies.
6. Display cost, savings, V2G reward, and the selected time slots.
7. Select one quoted plan and confirm a simulated advance card payment.

Station availability is updated through a protected status endpoint. A local
station simulator can produce the same events that a future OCPP adapter would
receive from physical chargers.

## Backend setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Edit `backend/.env` with the local PostgreSQL credentials, then run:

```powershell
cd backend
uvicorn app.main:app --reload
```

API documentation: <http://127.0.0.1:8000/docs>

## Frontend setup

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Dashboard: <http://127.0.0.1:5173>

## Energy data

The historical training set contains 131,158 complete Austrian 15-minute
observations from January 2015 to October 2018. Price, load, solar, and wind all
come from the same country. Recent observations can be imported separately and
do not change the fixed historical benchmark split.

To import the complete valid Austrian history again:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.import_energy_data `
  "PATH_TO\time_series_15min_singleindex.csv"
```

The importer updates existing timestamps instead of creating duplicates.
Negative electricity prices are preserved because they are valid market events.

## Main API routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Check the API process |
| GET | `/health/db` | Check PostgreSQL connectivity |
| POST | `/auth/register`, `/auth/login` | Create or access an account |
| GET/PATCH | `/me` | Read or edit the authenticated account |
| POST | `/me/change-password` | Change password after checking the current one |
| GET/POST | `/me/payment-method` | Read or save the masked default demo card |
| GET | `/catalog/vehicles` | List accepted EV models |
| GET/POST | `/vehicles` | List or add catalogue EVs to the account |
| GET | `/stations` | List preloaded Austrian stations |
| POST | `/stations/{id}/status` | Receive protected station availability events |
| GET/POST | `/charging-requests` | List or create charging needs |
| POST | `/optimization/{request_id}` | Run normal, V1G, or V2G optimization |
| POST | `/payments/checkout` | Confirm an advance demo payment for one plan |
| GET | `/ai/model-info` | Inspect the trained forecasting model and metrics |

## Optimization logic

The optimizer calculates the required energy from battery capacity and the SoC
difference. It builds an average daily 15-minute profile and ranks candidate slots
using:

```text
55% electricity price + 30% grid load - 15% renewable availability
```

Normal charging uses the earliest slots. V1G selects the lowest-score slots. V2G
adds a limited export during a high-value slot and includes the resulting reward.
The V2G result is a simulation and does not control physical charging hardware.

## AI energy forecasting

The DDM1 pipeline imports 131,158 complete Austrian 15-minute observations,
audits quality, creates a chronological 70/15/15 split, and measures a daily
profile baseline. Four HistGradientBoosting models forecast price, grid load,
solar generation, and wind generation from cyclical calendar, lag, and rolling
features. Training artifacts and metrics are generated with:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.analyze_energy_data
..\.venv\Scripts\python.exe -m scripts.train_energy_models
..\.venv\Scripts\python.exe -m scripts.backtest_energy_forecaster
```

The optimizer uses the trained forecast when available and automatically falls
back to the historical daily profile if the artifact cannot be loaded. The
backtest command evaluates recursive 24-hour predictions on weekly origins from
the held-out test period and compares them with a previous-day seasonal baseline.
The bundled training observations end in October 2018. To import recent Austrian
price, load, solar and wind data from the public Energy-Charts API (CC BY 4.0),
run from `backend`:

```powershell
..\.venv\Scripts\python.exe -m scripts.sync_energy_charts --days 10 --dry-run
..\.venv\Scripts\python.exe -m scripts.sync_energy_charts --days 10
..\.venv\Scripts\python.exe -m scripts.sync_energy_charts --days 10 --watch
```

The last command keeps a terminal running and refreshes every 15 minutes. The
importer refuses incomplete, discontinuous or data delayed by over three hours.
This is a delayed recent feed, not a real-time measurement. The optimizer falls
back to its historical profile when recent data expires. Current observations
do **not** establish current model accuracy: the trained model is still based on
2015-2018 and needs prospective validation before production use.

Run regression and end-to-end API tests with `pip install -r backend/requirements-dev.txt`
and, from `backend`, `..\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
See `docs/PROJECT_REPORT.md` and `docs/DEMO_SCRIPT.md` for the report and demo.

## Controlled project data

The EV catalogue contains the five models present in the supplied charging
dataset. Vehicle creation accepts a catalogue identifier, never a free-text
model. The active Austrian station seed is stored in
`backend/data/austria_charging_stations.csv` and loaded by migration 005. The
station identifiers, coordinates, operators, connectors, and charging power
come from Austria's national E-Control Ladestellenverzeichnis. This keeps the
station context consistent with the Austrian price, load, solar, and wind data.

## Station availability simulator

With the API running, send one simulated update for every active station:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.simulate_stations --once
```

Remove `--once` to keep sending updates every 30 seconds. The simulator calls
the protected station-status API using `STATION_API_KEY`. The frontend refreshes
availability every 30 seconds, ranks usable stations, marks the best available
choice as recommended, and prevents planning at full or offline stations.

Saved demo payment methods contain only a generated provider token, card brand,
last four digits, cardholder name, and expiry. Smart EV never stores the full
card number or CVC. A production deployment must replace the demo tokenization
with a PCI-compliant payment provider.
