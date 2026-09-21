"""Small regression checks for the deployed energy forecast safeguards."""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.ml.energy_forecaster import forecast_energy, predict_target


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


if __name__ == "__main__":
    unittest.main()
