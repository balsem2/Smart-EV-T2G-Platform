"""End-to-end API smoke test using an isolated in-memory database."""

import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import EnergyData, Station, VehicleCatalog


class UserJourneyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.session_factory() as db:
            db.add(VehicleCatalog(model="Test EV", battery_capacity=50, active=True))
            db.add(
                Station(
                    station_name="Test Station",
                    city="Wien",
                    power_kw=22,
                    active=True,
                    total_chargers=2,
                    available_chargers=1,
                    operational_status="online",
                    availability_source="simulated",
                )
            )
            for quarter in range(96):
                db.add(
                    EnergyData(
                        timestamp=datetime(2018, 9, 1) + timedelta(minutes=15 * quarter),
                        electricity_price=50 + quarter / 10,
                        grid_load=5000 + quarter,
                        solar_generation=100,
                        wind_generation=200,
                    )
                )
            db.commit()

        def isolated_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_register_vehicle_plan_and_advance_demo_payment(self):
        registered = self.client.post(
            "/auth/register",
            json={"name": "Demo User", "email": "demo@example.com", "password": "strong-pass-123"},
        )
        self.assertEqual(registered.status_code, 201, registered.text)
        token = registered.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        catalog = self.client.get("/catalog/vehicles").json()
        vehicle = self.client.post(
            "/vehicles",
            headers=headers,
            json={"catalog_id": catalog[0]["id"], "vehicle_age": 2},
        )
        self.assertEqual(vehicle.status_code, 201, vehicle.text)
        station = self.client.get("/stations").json()[0]
        departure = (datetime.now() + timedelta(hours=8)).isoformat()
        request = self.client.post(
            "/charging-requests",
            headers=headers,
            json={
                "vehicle_id": vehicle.json()["id"],
                "station_id": station["id"],
                "current_soc": 20,
                "target_soc": 40,
                "departure_time": departure,
            },
        )
        self.assertEqual(request.status_code, 201, request.text)
        request_id = request.json()["id"]

        schedules = {}
        for mode in ("normal", "v1g", "v2g"):
            response = self.client.post(
                f"/optimization/{request_id}", headers=headers, json={"mode": mode}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["forecast_source"], "historical_baseline")
            schedules[mode] = response.json()["schedule_id"]

        paid = self.client.post(
            "/payments/checkout",
            headers=headers,
            json={
                "schedule_id": schedules["v1g"],
                "payment_method": "test_card",
                "card_last4": "4242",
            },
        )
        self.assertEqual(paid.status_code, 201, paid.text)
        self.assertEqual(paid.json()["status"], "paid")
        self.assertEqual(
            self.client.post(
                "/payments/checkout",
                headers=headers,
                json={
                    "schedule_id": schedules["v1g"],
                    "payment_method": "test_card",
                    "card_last4": "4242",
                },
            ).status_code,
            409,
        )

    def test_recent_utc_observations_activate_ml_in_charging_plan(self):
        now_utc = datetime.now(timezone.utc)
        latest = now_utc.replace(second=0, microsecond=0)
        latest -= timedelta(minutes=latest.minute % 15 + 15)
        with self.session_factory() as db:
            for index in range(672):
                timestamp = latest - timedelta(minutes=15 * (671 - index))
                db.add(
                    EnergyData(
                        timestamp=timestamp.replace(tzinfo=None),
                        electricity_price=70 + index % 20,
                        grid_load=6000 + index % 100,
                        solar_generation=max(0, 300 - abs(timestamp.hour - 12) * 50),
                        wind_generation=200 + index % 50,
                    )
                )
            db.commit()

        registered = self.client.post(
            "/auth/register",
            json={"name": "Recent User", "email": "recent@example.com", "password": "strong-pass-123"},
        )
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        vehicle = self.client.post(
            "/vehicles", headers=headers, json={"catalog_id": 1, "vehicle_age": 1}
        )
        request = self.client.post(
            "/charging-requests",
            headers=headers,
            json={
                "vehicle_id": vehicle.json()["id"],
                "station_id": 1,
                "current_soc": 20,
                "target_soc": 40,
                "departure_time": (now_utc + timedelta(hours=8)).isoformat(),
            },
        )
        self.assertEqual(request.status_code, 201, request.text)
        result = self.client.post(
            f"/optimization/{request.json()['id']}",
            headers=headers,
            json={"mode": "v1g"},
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["forecast_source"], "machine_learning")
        self.assertTrue(result.json()["slots"][0]["timestamp"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
