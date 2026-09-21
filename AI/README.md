# Smart EV — Artificial Intelligence & Energy Forecasting Module

## 1. Academic & Industrial Overview

Electric Vehicle (EV) integration into the power grid introduces dual opportunities:
* **V1G (Smart Managed Charging)**: Time-shifting charging sessions to off-peak periods with low electricity prices, reduced grid strain, and high renewable penetration.
* **V2G (Vehicle-to-Grid)**: Bidirectional energy transfer allowing EV batteries to act as distributed energy storage resources, injecting energy into the grid during peak pricing and stress periods to earn economic rewards.

To operate V1G and V2G effectively, an energy management system cannot rely on static historical averages. It requires **accurate day-ahead continuous forecasting** across four critical grid variables:
1. **`electricity_price`** (€/MWh) — Day-ahead wholesale spot market price.
2. **`grid_load`** (MW) — Total national electrical demand.
3. **`solar_generation`** (MW) — Photovoltaic power injected into the transmission system.
4. **`wind_generation`** (MW) — Onshore wind turbine power generation.

---

## 2. Mathematical Formulation & EV Optimizer Integration

The Smart EV optimizer evaluates candidate quarter-hour charging slots $t \in [T_{\text{arrival}}, T_{\text{departure}}]$ using a composite grid score $S(t)$:

$$S(t) = w_p \cdot \tilde{P}(t) + w_l \cdot \tilde{L}(t) - w_r \cdot \tilde{R}(t)$$

Where:
* $w_p = 0.55$, $w_l = 0.30$, $w_r = 0.15$
* $\tilde{P}(t) \in [0, 1]$ is the min-max normalized predicted electricity price.
* $\tilde{L}(t) \in [0, 1]$ is the min-max normalized predicted grid load.
* $\tilde{R}(t) \in [0, 1]$ is the min-max normalized predicted total renewable generation:
  $$\tilde{R}(t) = \text{Norm}\Big(\hat{y}_{\text{solar}}(t) + \hat{y}_{\text{wind}}(t)\Big)$$

### Charging Strategies:
* **Normal Mode**: Earliest available slots $\min(t)$ until target battery State of Charge ($\text{SoC}$) is met.
* **V1G Mode**: Greedily allocates slots ordered by ascending composite score $\min S(t)$.
* **V2G Mode**: Charges during minimal score slots $\min S(t)$ and schedules a discharge of $E_{\text{discharge}} = \min(0.05 \cdot C_{\text{battery}}, P_{\text{station}} \times 0.25\text{h})$ during the maximum score slot $\max S(t)$ to maximize user reward:
  $$\text{Reward}_{\text{V2G}} = \max(0, \hat{P}_{\text{peak}}) \times \frac{E_{\text{discharge}}}{1000}$$

---

## 3. Dataset & Data Engineering (DDM1 Protocol)

* **Source**: Austrian Transmission Grid & Day-Ahead Spot Market (ENTSO-E & E-Control via OPSD).
* **Granularity**: 15 minutes (96 slots per day).
* **Volume**: 131,158 complete observations (January 1, 2015 to October 2, 2018); the timeline contains eight gaps.
* **Data Integrity**: Zero duplicated timestamps, negative electricity prices preserved (valid economic events reflecting extreme renewable surplus).
* **Strict Temporal Splitting** (Preventing lookahead data leakage):
  * **Train Set (70%)**: 91,810 samples (2015-01-01 to 2017-08-18)
  * **Validation Set (15%)**: 19,674 samples (2017-08-18 to 2018-03-11)
  * **Held-Out Test Set (15%)**: 19,674 samples (2018-03-11 to 2018-10-02)

---

## 4. Feature Engineering

Time-series features are extracted deterministically without future information:

### A. Cyclical Calendar Transformations
To maintain circular continuity (e.g. 23:45 is temporally close to 00:00, and December is adjacent to January), timestamps are mapped onto the unit circle:

$$\text{quarter\_sin} = \sin\left(\frac{2\pi \cdot q}{96}\right), \quad \text{quarter\_cos} = \cos\left(\frac{2\pi \cdot q}{96}\right)$$
$$\text{weekday\_sin} = \sin\left(\frac{2\pi \cdot d}{7}\right), \quad \text{weekday\_cos} = \cos\left(\frac{2\pi \cdot d}{7}\right)$$
$$\text{month\_sin} = \sin\left(\frac{2\pi \cdot (m - 1)}{12}\right), \quad \text{month\_cos} = \cos\left(\frac{2\pi \cdot (m - 1)}{12}\right)$$
$$\text{is\_weekend} = \mathbb{I}(d \ge 5)$$

### B. Autoregressive Lags & Rolling Statistics
* **Short & Medium Lags**: $t-15\text{min}$ (lag 1), $t-1\text{h}$ (lag 4), $t-24\text{h}$ (lag 96), $t-7\text{d}$ (lag 672).
* **Rolling Statistics**: 1-hour moving average ($\mu_4$) and 24-hour moving average ($\mu_{96}$).
* **Solar Stability Enhancement (V2 Innovation)**: For `solar_generation`, short lags accumulate error rapidly when recursive 24-hour day-ahead forecasting is performed across sunset and sunrise. V2 employs **daily lags** (`DAILY_LAGS` = 96, 192, 288, 384, 480, 576, 672) and cyclical solar position features, ensuring stable long-horizon forecasts.

---

## 5. Model Architectures & Benchmarking

The platform benchmarks multiple paradigms:
1. **Seasonal Slot Baseline**: Historical conditional averages $\mathbb{E}[y \mid \text{weekday}, \text{hour}, \text{minute}]$.
2. **Ridge Regression**: Linear model with $L_2$ regularization $\min \|y - Xw\|_2^2 + \alpha \|w\|_2^2$.
3. **Random Forest**: Non-linear bagging ensemble of randomized decision trees.
4. **HistGradientBoostingRegressor (V2 Production)**: Gradient-boosted decision trees with binning and early stopping.

### Evaluation Metrics:
* **MAE** (Mean Absolute Error): $\frac{1}{N} \sum |y_i - \hat{y}_i|$
* **RMSE** (Root Mean Squared Error): $\sqrt{\frac{1}{N} \sum (y_i - \hat{y}_i)^2}$
* **$R^2$ Score**: $1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$

---

## 6. How to Run & Reproduce

All commands can be executed from the project root:

### 1. Run the Multi-Model Benchmark:
```powershell
.\.venv\Scripts\python.exe AI/benchmark.py
```
Outputs:
* `AI/reports/benchmark_summary.json`
* `AI/reports/benchmark_summary.csv`
* `AI/reports/BENCHMARK_REPORT.md`

### 2. Train the Production V2 Models:
```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.train_energy_models
```

### 3. Run the 24-Hour Recursive Backtest:
```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.backtest_energy_forecaster
```
Outputs:
* `backend/reports/ddm1/recursive_24h_backtest.json`
* `backend/reports/ddm1/RECURSIVE_BACKTEST.md`

### Deployment limitation

The fixed training and backtest observations end in October 2018. A separate
Energy-Charts importer can add recent Austrian observations for inference; see
`backend/scripts/sync_energy_charts.py`. The importer does not retrain the model.
Live-input predictions remain unvalidated on 2026 data. When recent data is
missing or stale, optimization uses the historical baseline instead.

The deployed solar forecast is a conservative 50/50 blend of the V2 solar model
and the previous day's same-quarter observation. Its recursive 24-hour MAE
improvement over that seasonal baseline is small; see the backtest report.
