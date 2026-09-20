"""Create the reproducible DDM1 audit and chronological baseline report."""

import csv
import json
import math
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from statistics import mean, median, pstdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import EnergyData


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BACKEND_DIR / "reports" / "ddm1"
TARGETS = (
    "electricity_price",
    "grid_load",
    "solar_generation",
    "wind_generation",
)


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def descriptive_stats(values: list[float]) -> dict[str, float | int]:
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return {
        "count": len(values),
        "min": min(values),
        "q1": q1,
        "median": median(values),
        "mean": mean(values),
        "q3": q3,
        "max": max(values),
        "std": pstdev(values),
        "iqr_outliers": sum(value < lower or value > upper for value in values),
    }


def metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    errors = [value - estimate for value, estimate in zip(actual, predicted)]
    mae = mean(abs(error) for error in errors)
    rmse = math.sqrt(mean(error * error for error in errors))
    actual_mean = mean(actual)
    denominator = sum((value - actual_mean) ** 2 for value in actual)
    r2 = 1 - sum(error * error for error in errors) / denominator if denominator else 0
    return {"mae": mae, "rmse": rmse, "r2": r2}


def build_baseline(train_rows: list[EnergyData], test_rows: list[EnergyData]) -> dict:
    result = {}
    for target in TARGETS:
        by_slot: dict[tuple[int, int, int], list[float]] = defaultdict(list)
        by_time: dict[tuple[int, int], list[float]] = defaultdict(list)
        all_values: list[float] = []
        for row in train_rows:
            value = float(getattr(row, target))
            by_slot[(row.timestamp.weekday(), row.timestamp.hour, row.timestamp.minute)].append(value)
            by_time[(row.timestamp.hour, row.timestamp.minute)].append(value)
            all_values.append(value)
        slot_mean = {key: mean(values) for key, values in by_slot.items()}
        time_mean = {key: mean(values) for key, values in by_time.items()}
        global_mean = mean(all_values)
        actual = [float(getattr(row, target)) for row in test_rows]
        predicted = [
            slot_mean.get(
                (row.timestamp.weekday(), row.timestamp.hour, row.timestamp.minute),
                time_mean.get((row.timestamp.hour, row.timestamp.minute), global_mean),
            )
            for row in test_rows
        ]
        result[target] = metrics(actual, predicted)
    return result


def main() -> None:
    with Session(get_engine()) as session:
        rows = list(session.scalars(select(EnergyData).order_by(EnergyData.timestamp)))
    if not rows:
        raise RuntimeError("energy_data is empty")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    split_train = int(len(rows) * 0.70)
    split_validation = int(len(rows) * 0.85)
    train_rows = rows[:split_train]
    validation_rows = rows[split_train:split_validation]
    test_rows = rows[split_validation:]

    timestamps = [row.timestamp for row in rows]
    gap_count = 0
    missing_slots = 0
    for previous, current in zip(timestamps, timestamps[1:]):
        difference = current - previous
        if difference > timedelta(minutes=15):
            gap_count += 1
            missing_slots += max(0, int(difference.total_seconds() // 900) - 1)

    report = {
        "methodology": "DDM1 / CRISP-DM data understanding and baseline",
        "country": "Austria",
        "frequency_minutes": 15,
        "rows": len(rows),
        "start": timestamps[0].isoformat(),
        "end": timestamps[-1].isoformat(),
        "duplicate_timestamps": len(timestamps) - len(set(timestamps)),
        "gaps_over_15_minutes": gap_count,
        "estimated_missing_slots": missing_slots,
        "negative_price_rows": sum(row.electricity_price < 0 for row in rows),
        "statistics": {
            target: descriptive_stats([float(getattr(row, target)) for row in rows])
            for target in TARGETS
        },
        "chronological_split": {
            "train": {"rows": len(train_rows), "start": train_rows[0].timestamp.isoformat(), "end": train_rows[-1].timestamp.isoformat()},
            "validation": {"rows": len(validation_rows), "start": validation_rows[0].timestamp.isoformat(), "end": validation_rows[-1].timestamp.isoformat()},
            "test": {"rows": len(test_rows), "start": test_rows[0].timestamp.isoformat(), "end": test_rows[-1].timestamp.isoformat()},
        },
        "baseline_test_metrics": build_baseline(train_rows, test_rows),
        "recommended_features": [
            "hour_sin", "hour_cos", "weekday_sin", "weekday_cos", "month_sin", "month_cos", "is_weekend",
            "lag_15m", "lag_1h", "lag_24h", "lag_7d", "rolling_mean_1h", "rolling_mean_24h",
        ],
    }

    (REPORT_DIR / "energy_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    monthly: dict[str, list[EnergyData]] = defaultdict(list)
    profile: dict[tuple[int, int], list[EnergyData]] = defaultdict(list)
    for row in rows:
        monthly[row.timestamp.strftime("%Y-%m")].append(row)
        profile[(row.timestamp.hour, row.timestamp.minute)].append(row)

    with (REPORT_DIR / "monthly_summary.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["month", "observations", "avg_price_eur_mwh", "min_price_eur_mwh", "max_price_eur_mwh", "avg_load_mw", "avg_solar_mw", "avg_wind_mw"])
        for month, month_rows in sorted(monthly.items()):
            prices = [row.electricity_price for row in month_rows]
            writer.writerow([month, len(month_rows), mean(prices), min(prices), max(prices), mean(row.grid_load for row in month_rows), mean(row.solar_generation for row in month_rows), mean(row.wind_generation for row in month_rows)])

    with (REPORT_DIR / "daily_profile.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["time", "avg_price_eur_mwh", "avg_load_mw", "avg_solar_mw", "avg_wind_mw"])
        for (hour, minute), slot_rows in sorted(profile.items()):
            writer.writerow([f"{hour:02d}:{minute:02d}", mean(row.electricity_price for row in slot_rows), mean(row.grid_load for row in slot_rows), mean(row.solar_generation for row in slot_rows), mean(row.wind_generation for row in slot_rows)])

    markdown = f"""# Smart EV — DDM1 Energy Data Audit

## Scope

- Country: Austria
- Frequency: 15 minutes
- Observations: {report['rows']:,}
- Period: {report['start']} to {report['end']}
- Duplicate timestamps: {report['duplicate_timestamps']}
- Gaps longer than 15 minutes: {report['gaps_over_15_minutes']}
- Estimated missing 15-minute slots: {report['estimated_missing_slots']}
- Negative price observations preserved: {report['negative_price_rows']}

## Chronological split

| Split | Rows | Start | End |
| --- | ---: | --- | --- |
| Train | {len(train_rows):,} | {train_rows[0].timestamp} | {train_rows[-1].timestamp} |
| Validation | {len(validation_rows):,} | {validation_rows[0].timestamp} | {validation_rows[-1].timestamp} |
| Test | {len(test_rows):,} | {test_rows[0].timestamp} | {test_rows[-1].timestamp} |

## Baseline test metrics

| Target | MAE | RMSE | R² |
| --- | ---: | ---: | ---: |
"""
    for target, target_metrics in report["baseline_test_metrics"].items():
        markdown += f"| {target} | {target_metrics['mae']:.4f} | {target_metrics['rmse']:.4f} | {target_metrics['r2']:.4f} |\n"
    markdown += """

## Decision

The current daily-profile optimizer is retained as the baseline. A trained model
must improve validation and test MAE/RMSE before it can replace this fallback.
MAPE is not the primary metric because Austrian day-ahead prices can be zero or negative.
"""
    (REPORT_DIR / "README.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"report_dir": str(REPORT_DIR), "rows": len(rows), "baseline": report["baseline_test_metrics"]}, indent=2))


if __name__ == "__main__":
    main()
