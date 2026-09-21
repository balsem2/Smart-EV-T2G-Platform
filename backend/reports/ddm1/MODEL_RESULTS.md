# Smart EV — ML Model Results

These are chronological **one-step (15-minute-ahead)** test metrics. They must
not be presented as recursive 24-hour accuracy.

| Target | Baseline MAE | ML MAE | MAE improvement | ML RMSE | ML R² |
| --- | ---: | ---: | ---: | ---: | ---: |
| electricity_price | 15.8702 | 3.4530 | 78.2% | 9.4304 | 0.7674 |
| grid_load | 442.4753 | 36.1677 | 91.8% | 49.0169 | 0.9984 |
| solar_generation | 120.8079 | 39.1748 | 67.6% | 75.3890 | 0.9227 |
| wind_generation | 459.2637 | 25.7520 | 94.4% | 44.9767 | 0.9938 |


## Interpretation

The ML models beat the historical slot-average baseline for every target on the
held-out chronological test set. These are not day-ahead results. Run
`python -m scripts.backtest_energy_forecaster` to produce the separate recursive
24-hour evaluation before making day-ahead accuracy claims.
