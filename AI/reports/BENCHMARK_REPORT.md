# Smart EV — Energy Forecasting Benchmark Report

Evaluation of candidate models on the held-out Austrian test set (19,674 quarter-hour observations).

## Comparative Results by Target

### Electricity Price (€/MWh)

| Model | MAE | RMSE | R² | Train Time |
| --- | ---: | ---: | ---: | ---: |
| **Seasonal Baseline** | 16.0562 | 20.8274 | -0.1344 | 0.075s |
| **Ridge Regression** | 3.6281 | 9.9311 | 0.7421 | 0.16s |
| **Random Forest** | 4.5385 | 10.2082 | 0.7275 | 5.86s |
| **HistGradientBoosting (V2 Production)** | 3.4530 | 9.4304 | 0.7674 | 4.89s |

### Grid Load (MW)

| Model | MAE | RMSE | R² | Train Time |
| --- | ---: | ---: | ---: | ---: |
| **Seasonal Baseline** | 437.1978 | 572.8362 | 0.7877 | 0.075s |
| **Ridge Regression** | 55.8403 | 74.8887 | 0.9964 | 0.16s |
| **Random Forest** | 55.2854 | 72.5495 | 0.9966 | 5.86s |
| **HistGradientBoosting (V2 Production)** | 36.1677 | 49.0169 | 0.9984 | 4.89s |

### Solar Generation (MW)

| Model | MAE | RMSE | R² | Train Time |
| --- | ---: | ---: | ---: | ---: |
| **Seasonal Baseline** | 121.2828 | 192.5867 | 0.4954 | 0.075s |
| **Ridge Regression** | 37.1486 | 71.1278 | 0.9312 | 0.16s |
| **Random Forest** | 46.4370 | 86.1594 | 0.8990 | 5.86s |
| **HistGradientBoosting (V2 Production)** | 45.8762 | 86.2506 | 0.8988 | 4.89s |

### Wind Generation (MW)

| Model | MAE | RMSE | R² | Train Time |
| --- | ---: | ---: | ---: | ---: |
| **Seasonal Baseline** | 456.5530 | 571.1972 | 0.0074 | 0.075s |
| **Ridge Regression** | 23.0805 | 41.6903 | 0.9947 | 0.16s |
| **Random Forest** | 47.7866 | 77.1530 | 0.9819 | 5.86s |
| **HistGradientBoosting (V2 Production)** | 25.7499 | 44.9757 | 0.9938 | 4.89s |

## Key Findings & Academic Synthesis

1. These are one-step historical test metrics, not recursive 24-hour or current-period accuracy. See `backend/reports/ddm1/RECURSIVE_BACKTEST.md` for the deployed day-ahead test.
2. HistGradientBoosting has the lowest test MAE for price and load. Ridge is better for solar and wind on this one-step comparison; there is no universal winning architecture.
3. The deployed solar forecast is a 50/50 model/previous-day blend, which is not represented by the raw HistGradientBoosting row above. Its recursive 24-hour improvement is small and needs further validation.
