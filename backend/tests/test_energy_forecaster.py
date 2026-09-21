"""Small regression checks for the deployed energy forecast safeguards."""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.ml.energy_forecaster import forecast_energy, predict_target
from scripts.sync_energy_charts import latest_contiguous_window, merged_rows


class ConstantSolarModel:
    def predict(self, frame):
        return [100.0]


class EnergyForecasterTests(unittest.TestCase):
    def test_solar_blend_uses_only_previous_day_observation(self):
        bundle = {
            "models": {"solar_generation": ConstantSolarModel()},
            "feature_columns": ["solar_generation_lag_96"],
            "solar_blend_weight": 0.5,
        }
        result = predict_target(
            bundle, "solar_generation", {"solar_generation_lag_96": 40.0}
        )
        self.assertEqual(result, 70.0)

    def test_stale_history_is_rejected_before_model_load(self):
        start = datetime(2018, 10, 1)
        rows = [
            SimpleNamespace(timestamp=start + timedelta(minutes=15 * index))
            for index in range(672)
        ]
        with self.assertRaisesRegex(ValueError, "latest observed energy data"):
            forecast_energy(
                rows,
                datetime(2026, 9, 21),
                datetime(2026, 9, 22),
            )

    def test_live_source_join_uses_utc_timestamp_not_row_order(self):
        power = {
            "unit": "MW",
            "data": [
                {"timestamp": "2026-09-21T10:00:00+02:00", "values": {"load": 5000, "solar": 10, "wind_onshore": 20}},
                {"timestamp": "2026-09-21T10:15:00+02:00", "values": {"load": 5100, "solar": 11, "wind_onshore": 21}},
            ],
        }
        price = {
            "unit": "EUR / MWh",
            "data": [
                {"timestamp": "2026-09-21T08:15:00Z", "values": {"day_ahead_price": 100}},
                {"timestamp": "2026-09-21T08:00:00Z", "values": {"day_ahead_price": 90}},
            ],
        }
        rows = merged_rows(power, price)
        self.assertEqual([row["electricity_price"] for row in rows], [90, 100])
        self.assertEqual(len(latest_contiguous_window(rows)), 2)


if __name__ == "__main__":
    unittest.main()
