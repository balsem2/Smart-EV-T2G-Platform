# Recursive 24-hour backtest

This evaluation forecasts all 96 quarter-hour slots recursively: after the first
step, each prediction becomes input to the following step. It therefore measures
the real day-ahead behavior used by Smart EV, without using future observations.

- Held-out test period starts: 2018-03-13T17:00:00
- Weekly forecast origins evaluated: 29
- Predictions per target: 2784
- Baseline: same quarter-hour value from the previous day

| Target | Recursive MAE | Baseline MAE | MAE improvement | Recursive RMSE | R2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| electricity_price | 9.7624 | 15.6965 | 37.8% | 24.3922 | 0.2448 |
| grid_load | 379.5114 | 1369.4974 | 72.3% | 601.1830 | 0.7681 |
| solar_generation | 54.7349 | 35.3925 | -54.7% | 99.7875 | 0.8734 |
| wind_generation | 293.9612 | 454.2889 | 35.3% | 403.0264 | 0.5970 |


## Reading the result

These values are intentionally separate from the one-step 15-minute metrics.
The CSV and JSON reports also include errors at +15 minutes, +1 hour, +6 hours,
+12 hours, and +24 hours so forecast degradation can be inspected by horizon.
