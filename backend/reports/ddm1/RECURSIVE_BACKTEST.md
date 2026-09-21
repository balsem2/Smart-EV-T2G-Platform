# Recursive 24-hour backtest

This evaluation forecasts all 96 quarter-hour slots recursively: after the first
step, each prediction becomes input to the following step. It therefore measures
the real day-ahead behavior used by Smart EV, without using future observations.

- Held-out test period starts: 2018-03-15T16:00:00
- Weekly forecast origins evaluated: 29
- Predictions per target: 2784
- Baseline: same quarter-hour value from the previous day

| Target | Recursive MAE | Baseline MAE | MAE improvement | Recursive RMSE | R2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| electricity_price | 10.4425 | 15.8098 | 33.9% | 24.9471 | 0.2242 |
| grid_load | 366.0494 | 1373.8624 | 73.4% | 527.1340 | 0.8175 |
| solar_generation | 45.1043 | 38.9662 | -15.8% | 79.4521 | 0.9197 |
| wind_generation | 336.5476 | 486.6960 | 30.9% | 531.5865 | 0.2990 |


## Reading the result

These values are intentionally separate from the one-step 15-minute metrics.
The CSV and JSON reports also include errors at +15 minutes, +1 hour, +6 hours,
+12 hours, and +24 hours so forecast degradation can be inspected by horizon.
