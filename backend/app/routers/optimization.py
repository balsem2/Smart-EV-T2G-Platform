from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser
from app.ml.energy_forecaster import forecast_energy, model_metadata
from app.optimizer import optimize_charging


router = APIRouter(prefix="/optimization", tags=["Optimization"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/{request_id}", response_model=schemas.OptimizationResult)
def run_optimization(
    request_id: int,
    options: schemas.OptimizationRun,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.OptimizationResult:
    charging_request = crud.get_charging_request(database_session, request_id)
    if charging_request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charging request not found.")
    if charging_request.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charging request not found.")

    vehicle = crud.get_vehicle(database_session, charging_request.vehicle_id or 0)
    station = crud.get_station(database_session, charging_request.station_id or 0)
    if vehicle is None or station is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The charging request has an invalid vehicle or station.",
        )

    energy_rows = crud.list_recent_energy_data(database_session)
    try:
        forecast_rows = forecast_energy(
            energy_rows,
            charging_request.created_at or datetime.now(timezone.utc).replace(tzinfo=None),
            charging_request.departure_time,
        )
        forecast_model_name = model_metadata()["model_name"]
    except (FileNotFoundError, ValueError):
        forecast_rows = None
        forecast_model_name = None

    try:
        result = optimize_charging(
            charging_request,
            vehicle,
            station,
            energy_rows,
            options.mode,
            forecast_rows=forecast_rows,
            forecast_model_name=forecast_model_name,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    schedule = crud.save_optimization(database_session, request_id, result)
    database_session.refresh(current_user)
    return schemas.OptimizationResult(
        schedule_id=schedule.id,
        request_id=request_id,
        mode=result["mode"],
        predicted_energy_kwh=result["energy_needed"],
        predicted_duration_hours=result["predicted_duration"],
        cost_eur=result["cost"],
        saving_eur=result["saving"],
        v2g_energy_kwh=result["v2g_energy"],
        v2g_reward_eur=result["v2g_reward"],
        start_time=result["start_time"].replace(tzinfo=timezone.utc),
        end_time=result["end_time"].replace(tzinfo=timezone.utc),
        slots=[
            {**slot, "timestamp": slot["timestamp"].replace(tzinfo=timezone.utc)}
            for slot in result["slots"]
        ],
        wallet_balance=current_user.wallet_balance,
        reward_points=current_user.reward_points,
        forecast_source=result["forecast_source"],
        model_name=result["model_name"],
    )
