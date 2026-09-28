"""Safely recover a paid demo V2G reward missing from an older plan.

Recomputes the plan and refuses to write unless its cost and window match the
stored quote. Run without --apply first to inspect the comparison.
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud
from app.database import get_engine
from app.ml.energy_forecaster import forecast_energy, model_metadata
from app.models import ChargingRequest, ChargingSchedule, Payment, RewardEvent, Station, Vehicle
from app.optimizer import optimize_charging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schedule_id", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with Session(get_engine()) as db:
        schedule = db.get(ChargingSchedule, args.schedule_id)
        if schedule is None or schedule.mode != "v2g":
            parser.error("Schedule is missing or is not V2G")
        payment = db.scalar(
            select(Payment).where(Payment.schedule_id == schedule.id, Payment.status == "paid")
        )
        if payment is None:
            parser.error("This V2G plan has no successful demo payment")
        if db.scalar(select(RewardEvent).where(RewardEvent.schedule_id == schedule.id)):
            parser.error("Reward already credited; no changes made")
        request = db.get(ChargingRequest, schedule.request_id)
        vehicle = db.get(Vehicle, request.vehicle_id) if request else None
        station = db.get(Station, request.station_id) if request else None
        if request is None or vehicle is None or station is None:
            parser.error("Cannot reconstruct the original plan")

        energy_rows = crud.list_recent_energy_data(db)
        try:
            forecast_rows = forecast_energy(
                energy_rows, request.created_at, request.departure_time
            )
            model_name = model_metadata()["model_name"]
        except (FileNotFoundError, ValueError):
            forecast_rows, model_name = None, None
        try:
            result = optimize_charging(
                request, vehicle, station, energy_rows, "v2g",
                forecast_rows=forecast_rows, forecast_model_name=model_name,
            )
        except ValueError as error:
            parser.error(f"Cannot reconstruct the original plan: {error}")

        print(f"Stored cost: EUR {schedule.cost:.4f}; reconstructed: EUR {result['cost']:.4f}")
        if (
            abs(schedule.cost - result["cost"]) > 0.0001
            or schedule.start_time != result["start_time"]
            or schedule.end_time != result["end_time"]
        ):
            parser.error("Original quote differs from current reconstruction; no changes made")
        print(
            f"Verified simulated export: {result['v2g_energy']:.4f} kWh; "
            f"reward: EUR {result['v2g_reward']:.4f}"
        )
        if not args.apply:
            print("Dry run only. Add --apply to credit this existing demo plan.")
            return
        schedule.v2g_energy_kwh = result["v2g_energy"]
        schedule.v2g_reward_eur = result["v2g_reward"]
        crud.credit_demo_v2g_reward(db, schedule, payment.user_id)
        db.commit()
        print("Simulated V2G reward credited once.")


if __name__ == "__main__":
    main()
