# Smart EV - Transportation-to-Grid Platform

Local development URLs:

- Web app: `http://smart-ev.localhost:5173`
- API: `http://api.smart-ev.localhost:8000`
- API documentation: `http://api.smart-ev.localhost:8000/docs`

The `.localhost` domain is reserved for local development and resolves to the
current computer without changing the Windows hosts file.

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
3. Select a compatible Austrian station directly from the interactive map.
4. Submit current SoC, target SoC, and departure time.
5. Compare normal and V1G charging, then pay in advance to reserve the exact slot.
6. Use the separate V2G service only with a configured bidirectional vehicle and station.
7. Follow reservation, operator and meter-confirmation events from notifications.

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
| POST | `/payments/stripe/checkout-session` | Start a Stripe-hosted test checkout |
| POST | `/payments/stripe/confirm/{session_id}` | Verify a returned Stripe test payment |
| GET | `/payments`, `/payments/{id}/invoice` | Payment and invoice history |
| POST | `/auth/verify-email`, `/auth/resend-verification` | Email verification |
| POST | `/auth/forgot-password`, `/auth/reset-password` | Expiring password reset flow |
| GET/DELETE | `/reservations` | List or cancel the authenticated user's reservations |
| GET/PATCH | `/notifications` | List and acknowledge account notifications |
| POST | `/v2g-offers` | Request a compatibility-checked V2G grid offer |
| GET | `/operator/dashboard` | View bookings and V2G jobs for one managed station |
| GET | `/ai/model-info` | Inspect the trained forecasting model and metrics |

Migration `018_reservations_v2g_operator_notifications.sql` adds the required
tables and capability flags. For the academic operator console, run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.seed_demo_operator
```

The local demonstration account is `operator@smart-ev.at` with password
`SmartEV-Operator-2026`. Change or remove it before any non-local deployment.

## Stripe test checkout and email

Add a Stripe **test-mode** secret key to `backend/.env` to enable hosted test
checkout and Stripe invoice creation:

```env
STRIPE_SECRET_KEY=sk_test_...
FRONTEND_URL=http://smart-ev.localhost:5173
```

Use Stripe's documented test card `4242 4242 4242 4242`, a future expiry date
and any CVC on the Stripe-hosted page. Never enter a real card in test mode.
Without a Stripe key, Smart EV keeps the local academic checkout available.

Email verification tokens expire after 24 hours and password-reset tokens after
30 minutes; both are single-use. For the local demo, start the included SMTP
catcher from the project root in another terminal:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.local_mail_server
```

Then open <http://localhost:8025> to read verification and password-reset emails.
The local catcher never contacts an external email provider. A deployed environment
must replace the local `SMTP_*` values with authenticated provider credentials.

For a confirmed **V2G demo** plan, checkout credits the quoted simulated
export reward to the demo wallet and 10 points per simulated kWh. Normal and
Smart V1G plans do not earn V2G rewards. This is a software simulation:
reservations are stored by the platform, but no physical charger is controlled
and no real-money transfer occurs.
Smart V1G separately earns one point per euro cent saved. At checkout, users
may redeem points in bundles of 100 (`100 points = EUR 1`) as a discount on a
new demo charging plan; points cannot be withdrawn as real money.
Existing plans made before migration `009_v2g_reward_quotes.sql` lack a saved
reward quote and cannot be credited automatically without reconstructing and
verifying the original quote.

## Optimization logic

The optimizer calculates the required energy from battery capacity and the SoC
difference. Users choose both an earliest charging start and a ready-by deadline,
so future sessions can be planned from home. It builds an average daily 15-minute
profile and ranks candidate slots using:

```text
55% electricity price + 30% grid load - 15% renewable availability
```

Normal charging uses the earliest slots. V1G selects the lowest-score slots. V2G
adds a limited export during a high-value slot and includes the resulting reward.
The V2G result is a simulation and does not control physical charging hardware.
Smart V1G and V2G each return three selectable variants: balanced, lowest cost,
and greenest. Every option shows its exact Austrian-time charging windows before
the user confirms the demo reservation and payment.

## AI energy forecasting

The DDM1 pipeline contains 131,158 complete Austrian 15-minute observations.
V3 enriches them with regional-average Open-Meteo temperature, cloud cover,
solar radiation, 100 m wind and precipitation. It uses a chronological 70/15/15
split and direct horizons from 15 minutes to 24 hours, so one prediction is not
fed recursively into the next. Ridge and HistGradientBoosting compete separately
for each energy target; the validation winner is tested on later unseen data.
Quantile models also provide an empirical 80% prediction interval.

The customer-facing assistant now requests Austria's published 15-minute
day-ahead market prices from Energy-Charts and aggregates them into an hourly
price view. Published prices replace the model's price estimate only for the
timestamps actually returned by the public source; missing periods remain
clearly labelled as AI forecasts. Grid load, solar and wind remain model
forecasts and are combined with price to rank the best continuous one-hour
charging window. These are wholesale EUR/MWh prices, not a charging-station
retail tariff. The platform never invents operator fees that are absent from
the source data.

Training artifacts and metrics are generated with:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.analyze_energy_data
..\.venv\Scripts\python.exe -m scripts.sync_weather --start 2015-01-01 --end 2018-10-03
..\.venv\Scripts\python.exe -m scripts.train_direct_energy_models
```

The optimizer uses the trained forecast when available and automatically falls
back to the historical daily profile if the artifact cannot be loaded. The
bundled continuous training observations end in October 2018. Recent rows are
kept in a separate continuous segment until enough have accumulated for safe
retraining; the multi-year gap is never silently interpolated. To import recent Austrian
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

The current charger counts are **demo estimates**, not live occupancy. The
station CSV contains locations and charging power, but no live connector counts.
The frontend labels simulated counts accordingly. Do not treat the demo counts
as a real-world reservation or guaranteed availability.

E-Control publishes a [public charging-station API](https://www.e-control.at/ladestellenverzeichnis-technische-informationen)
with live status. To prepare access, register an API key and a domain at
https://admin.ladestellen.at/#/api/registrieren, then set `ECONTROL_API_KEY`
and `ECONTROL_REFERER` (the exact registered HTTPS domain) in `backend/.env`.
Do not commit the key. Verify access with:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.check_econtrol_access
```

This probe calls E-Control's documented `/search` endpoint and reports only
the response structure. It does **not** update station availability. The
response schema and identifier mapping still need confirmation from an
authenticated sample before the live feed can safely replace simulation.

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
