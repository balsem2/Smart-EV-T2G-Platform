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
| electricity_price | 10.4415 | 15.8098 | 34.0% | 24.9488 | 0.2241 |
| grid_load | 364.9807 | 1373.8624 | 73.4% | 523.2766 | 0.8201 |
| solar_generation | 38.7119 | 38.9662 | 0.7% | 71.5437 | 0.9349 |
| wind_generation | 345.4044 | 486.6960 | 29.0% | 535.3272 | 0.2891 |


## Reading the result

These values are intentionally separate from the one-step 15-minute metrics.
The CSV and JSON reports also include errors at +15 minutes, +1 hour, +6 hours,
+12 hours, and +24 hours so forecast degradation can be inspected by horizon.
The deployed solar value is a 50/50 blend of the V2 model and the previous-day
same-slot observation. Its small gain should not be interpreted as evidence of
reliable live performance; fresh data and further validation are still needed.
