"""End-to-end API smoke test using an isolated in-memory database."""

import unittest
from math import floor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ChargingRequest, ChargingSchedule, EnergyData, Station, User, VehicleCatalog
from app.routers.charging_requests import _connectors_are_compatible


class UserJourneyTests(unittest.TestCase):
    def register_verified(self, name: str, email: str, password: str = "strong-pass-123"):
        registered = self.client.post(
            "/auth/register", json={"name": name, "email": email, "password": password}
        )
        self.assertEqual(registered.status_code, 201, registered.text)
        token = registered.json()["development_token"]
        verified = self.client.post("/auth/verify-email", json={"token": token})
        self.assertEqual(verified.status_code, 200, verified.text)
        logged_in = self.client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        return logged_in

    def test_connector_compatibility_matches_vehicle_and_station_types(self):
        self.assertTrue(_connectors_are_compatible("Type 2 AC,CCS2 DC", "Type 2 AC"))
        self.assertFalse(_connectors_are_compatible("Type 1 AC,CCS1 DC", "Type 2 AC"))

    def test_separate_v2g_offer_respects_reserve_and_credits_reward_once(self):
        registered = self.register_verified("Grid Helper", "grid@example.com")
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        vehicle = self.client.post(
            "/vehicles", headers=headers, json={"catalog_id": 1, "vehicle_age": 1}
        ).json()
        response = self.client.post(
            "/v2g-offers",
            headers=headers,
            json={
                "vehicle_id": vehicle["id"],
                "station_id": 1,
                "current_soc": 80,
                "minimum_soc": 60,
                "available_until": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        offer = response.json()
        self.assertGreater(offer["export_energy_kwh"], 0)
        self.assertLessEqual(offer["export_energy_kwh"], 50 * 0.20)
        self.assertTrue(offer["export_start"].endswith("Z"))
        accepted = self.client.post(
            f"/v2g-offers/{offer['id']}/accept", headers=headers, json={}
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertEqual(self.client.get("/me", headers=headers).json()["wallet_balance"], 0)
        completed = self.client.post(
            f"/v2g-offers/{offer['id']}/simulate-delivery", headers=headers, json={}
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(completed.json()["delivered_energy_kwh"], offer["export_energy_kwh"])
        profile = self.client.get("/me", headers=headers).json()
        self.assertEqual(profile["wallet_balance"], round(offer["reward_eur"], 2))
        self.assertEqual(
            self.client.post(f"/v2g-offers/{offer['id']}/simulate-delivery", headers=headers, json={}).status_code,
            409,
        )

    def setUp(self):
        # API tests must stay isolated from a locally running SMTP demo service.
        self.email_patcher = patch("app.routers.auth.send_account_email", return_value=False)
        self.email_patcher.start()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.session_factory() as db:
            db.add(VehicleCatalog(model="Test EV", battery_capacity=50, active=True, supports_v2g=True))
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
                    supports_v2g=True,
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
        self.email_patcher.stop()

    def test_register_vehicle_plan_and_advance_demo_payment(self):
        registered = self.register_verified("Demo User", "demo@example.com")
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
        quotes = {}
        for mode in ("normal", "v1g", "v2g"):
            response = self.client.post(
                f"/optimization/{request_id}", headers=headers, json={"mode": mode}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["forecast_source"], "historical_baseline")
            schedules[mode] = response.json()["schedule_id"]
            quotes[mode] = response.json()

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
        reservations = self.client.get("/reservations", headers=headers)
        self.assertEqual(reservations.status_code, 200, reservations.text)
        self.assertEqual(len(reservations.json()), 1)
        self.assertEqual(reservations.json()[0]["station_id"], station["id"])
        notifications = self.client.get("/notifications", headers=headers)
        self.assertEqual(notifications.status_code, 200, notifications.text)
        self.assertEqual(notifications.json()[0]["type"], "reservation")
        marked = self.client.patch(
            f"/notifications/{notifications.json()[0]['id']}/read", headers=headers, json={}
        )
        self.assertIsNotNone(marked.json()["read_at"])
        payment_history = self.client.get("/payments", headers=headers)
        self.assertEqual(len(payment_history.json()), 1)
        invoice = self.client.get(
            f"/payments/{payment_history.json()[0]['id']}/invoice", headers=headers
        )
        self.assertEqual(invoice.status_code, 200, invoice.text)
        self.assertEqual(invoice.json()["reference"], paid.json()["reference"])
        self.assertEqual(invoice.json()["amount_paid"], paid.json()["amount"])
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

        before = self.client.get("/me", headers=headers).json()
        v1g_rewards = self.client.get("/me/rewards", headers=headers).json()
        expected_v1g_points = floor(round(max(quotes["v1g"]["saving_eur"], 0), 2) * 100 + 0.5)
        self.assertEqual(len(v1g_rewards), 1 if expected_v1g_points else 0)
        if v1g_rewards:
            self.assertEqual(v1g_rewards[0]["reward_type"], "v1g_saving")
            self.assertEqual(v1g_rewards[0]["saving_eur"], round(quotes["v1g"]["saving_eur"], 2))
        self.assertEqual(before["reward_points"], expected_v1g_points)
        self.assertEqual(before["wallet_balance"], 0)
        v2g_quote = self.client.post(
            f"/optimization/{request_id}", headers=headers, json={"mode": "v2g"}
        ).json()
        charged_energy = sum(
            slot["energy_kwh"] for slot in v2g_quote["slots"] if slot["action"] == "charge"
        )
        exported_energy = -sum(
            slot["energy_kwh"] for slot in v2g_quote["slots"] if slot["action"] == "discharge"
        )
        self.assertAlmostEqual(
            charged_energy - exported_energy,
            v2g_quote["predicted_energy_kwh"],
            places=3,
        )
        self.assertAlmostEqual(
            v2g_quote["cost_eur"] - v2g_quote["v2g_reward_eur"],
            v2g_quote["net_cost_eur"],
            places=3,
        )
        v2g_paid = self.client.post(
            "/payments/checkout",
            headers=headers,
            json={
                "schedule_id": v2g_quote["schedule_id"],
                "payment_method": "test_card",
                "card_last4": "4242",
            },
        )
        self.assertEqual(v2g_paid.status_code, 201, v2g_paid.text)
        self.assertEqual(v2g_paid.json()["amount"], round(v2g_quote["cost_eur"], 2))
        rewards = self.client.get("/me/rewards", headers=headers).json()
        after = self.client.get("/me", headers=headers).json()
        self.assertEqual(len(rewards), len(v1g_rewards) + 1)
        v2g_reward = next(reward for reward in rewards if reward["reward_type"] == "v2g_export")
        self.assertAlmostEqual(v2g_reward["energy_returned"], v2g_quote["v2g_energy_kwh"])
        self.assertEqual(v2g_reward["reward"], round(v2g_quote["v2g_reward_eur"], 2))
        self.assertEqual(
            after["wallet_balance"],
            round(before["wallet_balance"] + v2g_reward["reward"], 2),
        )
        self.assertGreater(after["reward_points"], before["reward_points"])
        self.assertEqual(
            self.client.post(
                "/payments/checkout",
                headers=headers,
                json={
                    "schedule_id": v2g_quote["schedule_id"],
                    "payment_method": "test_card",
                    "card_last4": "4242",
                },
            ).status_code,
            409,
        )
        self.assertEqual(len(self.client.get("/me/rewards", headers=headers).json()), len(v1g_rewards) + 1)

    def test_email_verification_and_password_reset_tokens_are_single_use(self):
        registered = self.client.post(
            "/auth/register",
            json={"name": "Secure User", "email": "secure@example.com", "password": "old-password-123"},
        )
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertEqual(registered.json()["email"], "secure@example.com")
        verification_token = registered.json()["development_token"]
        self.assertEqual(
            self.client.post(
                "/auth/login",
                json={"email": "secure@example.com", "password": "old-password-123"},
            ).status_code,
            403,
        )
        verified = self.client.post("/auth/verify-email", json={"token": verification_token})
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertEqual(
            self.client.post("/auth/verify-email", json={"token": verification_token}).status_code,
            400,
        )
        reset_request = self.client.post(
            "/auth/forgot-password", json={"email": "secure@example.com"}
        )
        reset_token = reset_request.json()["development_token"]
        reset = self.client.post(
            "/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "new-password-123",
                "confirm_password": "new-password-123",
            },
        )
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(
            self.client.post(
                "/auth/login",
                json={"email": "secure@example.com", "password": "new-password-123"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/auth/reset-password",
                json={
                    "token": reset_token,
                    "new_password": "another-password-123",
                    "confirm_password": "another-password-123",
                },
            ).status_code,
            400,
        )

    def test_smart_v1g_positive_saving_credits_points_once_without_cash_reward(self):
        registered = self.register_verified("Saver", "saver@example.com")
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        vehicle = self.client.post(
            "/vehicles", headers=headers, json={"catalog_id": 1, "vehicle_age": 1}
        )
        charging_request = self.client.post(
            "/charging-requests",
            headers=headers,
            json={
                "vehicle_id": vehicle.json()["id"],
                "station_id": 1,
                "current_soc": 20,
                "target_soc": 40,
                "departure_time": (datetime.now() + timedelta(hours=8)).isoformat(),
            },
        )
        with self.session_factory() as db:
            quote = ChargingSchedule(
                request_id=charging_request.json()["id"],
                mode="v1g",
                cost=1.07,
                saving=0.84,
                status="quoted",
            )
            db.add(quote)
            db.commit()
            schedule_id = quote.id
        paid = self.client.post(
            "/payments/checkout",
            headers=headers,
            json={"schedule_id": schedule_id, "payment_method": "test_card", "card_last4": "4242"},
        )
        self.assertEqual(paid.status_code, 201, paid.text)
        profile = self.client.get("/me", headers=headers).json()
        rewards = self.client.get("/me/rewards", headers=headers).json()
        self.assertEqual(profile["reward_points"], 84)
        self.assertEqual(profile["wallet_balance"], 0)
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0]["reward_type"], "v1g_saving")
        self.assertEqual(rewards[0]["saving_eur"], 0.84)
        self.assertEqual(rewards[0]["points"], 84)
        self.assertEqual(
            self.client.post(
                "/payments/checkout", headers=headers,
                json={"schedule_id": schedule_id, "payment_method": "test_card", "card_last4": "4242"},
            ).status_code,
            409,
        )
        self.assertEqual(self.client.get("/me", headers=headers).json()["reward_points"], 84)

    def test_points_redeem_in_hundreds_and_reduce_demo_payment(self):
        registered = self.register_verified("Redeemer", "redeemer@example.com")
        user_id = registered.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        with self.session_factory() as db:
            user = db.get(User, user_id)
            user.reward_points = 250
            request = ChargingRequest(
                user_id=user_id,
                station_id=1,
                current_soc=20,
                target_soc=40,
                departure_time=datetime.now() + timedelta(hours=4),
            )
            db.add(request)
            db.flush()
            quote = ChargingSchedule(
                request_id=request.id,
                mode="normal",
                cost=2.49,
                saving=0,
                status="quoted",
            )
            db.add(quote)
            db.commit()
            schedule_id = quote.id

        paid = self.client.post(
            "/payments/checkout",
            headers=headers,
            json={
                "schedule_id": schedule_id,
                "payment_method": "test_card",
                "card_last4": "4242",
                "redeem_points": True,
            },
        )
        self.assertEqual(paid.status_code, 201, paid.text)
        receipt = paid.json()
        self.assertEqual(receipt["original_amount"], 2.49)
        self.assertEqual(receipt["points_redeemed"], 200)
        self.assertEqual(receipt["points_discount_eur"], 2)
        self.assertEqual(receipt["amount"], 0.49)
        self.assertEqual(self.client.get("/me", headers=headers).json()["reward_points"], 50)

    def test_future_start_and_smart_variants_return_selectable_schedules(self):
        registered = self.register_verified("Planner", "planner@example.com")
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        vehicle = self.client.post(
            "/vehicles", headers=headers, json={"catalog_id": 1, "vehicle_age": 1}
        )
        earliest = datetime.now(timezone.utc) + timedelta(hours=1)
        ready_by = earliest + timedelta(hours=8)
        charging_request = self.client.post(
            "/charging-requests",
            headers=headers,
            json={
                "vehicle_id": vehicle.json()["id"],
                "station_id": 1,
                "current_soc": 20,
                "target_soc": 40,
                "earliest_start_time": earliest.isoformat(),
                "departure_time": ready_by.isoformat(),
            },
        )
        self.assertEqual(charging_request.status_code, 201, charging_request.text)
        self.assertIsNotNone(charging_request.json()["earliest_start_time"])

        schedules = []
        for variant in ("balanced", "lowest_cost", "greenest"):
            response = self.client.post(
                f"/optimization/{charging_request.json()['id']}",
                headers=headers,
                json={"mode": "v1g", "variant": variant},
            )
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["variant"], variant)
            self.assertTrue(result["slots"])
            self.assertTrue(
                all(datetime.fromisoformat(slot["timestamp"]) >= earliest for slot in result["slots"])
            )
            timestamps = [datetime.fromisoformat(slot["timestamp"]) for slot in result["slots"]]
            self.assertTrue(
                all(
                    timestamps[index + 1] - timestamps[index] == timedelta(minutes=15)
                    for index in range(len(timestamps) - 1)
                )
            )
            schedules.append(result["schedule_id"])
        self.assertEqual(len(set(schedules)), 3)

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

        registered = self.register_verified("Recent User", "recent@example.com")
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
