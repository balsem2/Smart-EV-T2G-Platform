# Smart EV — ML Model Results

These are chronological **one-step (15-minute-ahead)** test metrics. They must
not be presented as recursive 24-hour accuracy.

| Target | Baseline MAE | ML MAE | MAE improvement | ML RMSE | ML R² |
| --- | ---: | ---: | ---: | ---: | ---: |
| electricity_price | 15.8702 | 3.5959 | 77.3% | 9.4914 | 0.7632 |
| grid_load | 442.4753 | 35.3651 | 92.0% | 48.0550 | 0.9985 |
| solar_generation | 120.8079 | 12.5870 | 89.6% | 33.1528 | 0.9850 |
| wind_generation | 459.2637 | 25.7544 | 94.4% | 44.9351 | 0.9938 |


## Interpretation

The ML models beat the historical slot-average baseline for every target on the
held-out chronological test set. These are not day-ahead results. The completed
recursive day-ahead evaluation is documented in `RECURSIVE_BACKTEST.md`.
