# Smart EV — DDM1 Energy Data Audit

## Scope

- Country: Austria
- Frequency: 15 minutes
- Observations: 131,158
- Period: 2015-01-01T07:15:00 to 2018-10-02T21:30:00
- Duplicate timestamps: 0
- Gaps longer than 15 minutes: 8
- Estimated missing 15-minute slots: 420
- Negative price observations preserved: 2245

## Chronological split

| Split | Rows | Start | End |
| --- | ---: | --- | --- |
| Train | 91,810 | 2015-01-01 07:15:00 | 2017-08-18 22:30:00 |
| Validation | 19,674 | 2017-08-18 22:45:00 | 2018-03-11 21:00:00 |
| Test | 19,674 | 2018-03-11 21:15:00 | 2018-10-02 21:30:00 |

## Baseline test metrics

| Target | MAE | RMSE | R² |
| --- | ---: | ---: | ---: |
| electricity_price | 15.8702 | 20.6465 | -0.1283 |
| grid_load | 442.4753 | 576.5068 | 0.7876 |
| solar_generation | 120.8079 | 193.1828 | 0.4863 |
| wind_generation | 459.2637 | 573.9047 | 0.0068 |


## Decision

The current daily-profile optimizer is retained as the baseline. A trained model
must improve validation and test MAE/RMSE before it can replace this fallback.
MAPE is not the primary metric because Austrian day-ahead prices can be zero or negative.
