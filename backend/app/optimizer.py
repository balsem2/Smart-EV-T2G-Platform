from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Literal

from app.models import ChargingRequest, EnergyData, Station, Vehicle


SLOT_DURATION_HOURS = 0.25
OptimizationMode = Literal["normal", "v1g", "v2g"]
OptimizationVariant = Literal["balanced", "lowest_cost", "greenest"]


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.0
    return (value - minimum) / (maximum - minimum)


def _round_up_to_quarter_hour(value: datetime) -> datetime:
    rounded = value.replace(second=0, microsecond=0)
    remainder = rounded.minute % 15
    if remainder or value.second or value.microsecond:
        rounded += timedelta(minutes=15 - remainder)
    return rounded


def _build_daily_profile(
    energy_rows: list[EnergyData],
) -> dict[tuple[int, int], dict[str, float]]:
    buckets: dict[tuple[int, int], list[EnergyData]] = defaultdict(list)
    for row in energy_rows:
        if row.timestamp is not None:
            buckets[(row.timestamp.hour, row.timestamp.minute)].append(row)

    profile: dict[tuple[int, int], dict[str, float]] = {}
    for key, rows in buckets.items():
        profile[key] = {
            "price": sum(row.electricity_price or 0 for row in rows) / len(rows),
            "load": sum(row.grid_load or 0 for row in rows) / len(rows),
            "renewable": sum(
                (row.solar_generation or 0) + (row.wind_generation or 0)
                for row in rows
            )
            / len(rows),
        }
    return profile


def optimize_charging(
    charging_request: ChargingRequest,
    vehicle: Vehicle,
    station: Station,
    energy_rows: list[EnergyData],
    mode: OptimizationMode,
    variant: OptimizationVariant = "balanced",
    forecast_rows: list[dict] | None = None,
    forecast_model_name: str | None = None,
) -> dict:
    if not energy_rows:
        raise ValueError("Energy data is empty.")
    if vehicle.battery_capacity is None or vehicle.battery_capacity <= 0:
        raise ValueError("The vehicle battery capacity is invalid.")
    if station.power_kw is None or station.power_kw <= 0:
        raise ValueError("The station power is invalid.")
    if charging_request.current_soc is None or charging_request.target_soc is None:
        raise ValueError("The charging request SoC values are missing.")
    if charging_request.departure_time is None:
        raise ValueError("The departure time is missing.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    requested_start = charging_request.earliest_start_time or charging_request.created_at or now
    arrival_time = _round_up_to_quarter_hour(max(requested_start, now))
    if charging_request.departure_time <= arrival_time:
        raise ValueError("The departure time must be after the charging request.")

    energy_needed = vehicle.battery_capacity * (
        charging_request.target_soc - charging_request.current_soc
    ) / 100
    profile = _build_daily_profile(energy_rows)
    if not profile:
        raise ValueError("Energy data does not contain a usable daily profile.")

    forecast_by_timestamp = {
        row["timestamp"]: {
            "price": row["electricity_price"],
            "load": row["grid_load"],
            "renewable": row["solar_generation"] + row["wind_generation"],
        }
        for row in (forecast_rows or [])
    }
    candidate_slots = []
    timestamp = arrival_time
    while timestamp < charging_request.departure_time:
        metrics = forecast_by_timestamp.get(timestamp)
        if metrics is None:
            metrics = profile.get((timestamp.hour, timestamp.minute))
        if metrics is not None:
            candidate_slots.append({"timestamp": timestamp, **metrics})
        timestamp += timedelta(minutes=15)

    if not candidate_slots:
        raise ValueError("No energy profile is available before departure.")

    prices = [slot["price"] for slot in candidate_slots]
    loads = [slot["load"] for slot in candidate_slots]
    renewables = [slot["renewable"] for slot in candidate_slots]
    for slot in candidate_slots:
        slot["score"] = (
            0.55 * _normalize(slot["price"], min(prices), max(prices))
            + 0.30 * _normalize(slot["load"], min(loads), max(loads))
            - 0.15
            * _normalize(slot["renewable"], min(renewables), max(renewables))
        )

    slot_capacity = station.power_kw * SLOT_DURATION_HOURS

    def allocate(slots: list[dict], required_energy: float) -> list[dict]:
        remaining = required_energy
        allocations = []
        for slot in slots:
            if remaining <= 1e-9:
                break
            energy = min(slot_capacity, remaining)
            allocations.append(
                {
                    "timestamp": slot["timestamp"],
                    "action": "charge",
                    "energy_kwh": round(energy, 4),
                    "power_kw": station.power_kw,
                    "price_eur_per_mwh": round(slot["price"], 4),
                }
            )
            remaining -= energy
        if remaining > 1e-6:
            raise ValueError("Not enough time to reach the target SoC before departure.")
        return allocations

    def allocate_contiguous(
        slots: list[dict],
        required_energy: float,
        strategy: OptimizationVariant,
        leave_export_slot: bool = False,
    ) -> list[dict]:
        """Choose one uninterrupted charging window for a user-friendly plan."""
        required_slot_count = ceil(required_energy / slot_capacity)
        windows = []
        for index in range(len(slots) - required_slot_count + 1):
            window = slots[index : index + required_slot_count]
            if any(
                window[position + 1]["timestamp"] - window[position]["timestamp"]
                != timedelta(minutes=15)
                for position in range(len(window) - 1)
            ):
                continue
            window_end = window[-1]["timestamp"] + timedelta(minutes=15)
            if leave_export_slot and not any(slot["timestamp"] >= window_end for slot in slots):
                continue
            if strategy == "lowest_cost":
                ranking = sum(slot["price"] for slot in window) / len(window)
            elif strategy == "greenest":
                ranking = -sum(slot["renewable"] for slot in window) / len(window)
            else:
                ranking = sum(slot["score"] for slot in window) / len(window)
            windows.append((ranking, window[0]["timestamp"], window))
        if not windows:
            raise ValueError("No continuous charging window is available before departure.")
        selected_window = min(windows, key=lambda item: (item[0], item[1]))[2]
        return allocate(selected_window, required_energy)

    normal_slots = allocate(candidate_slots, energy_needed)
    normal_cost = sum(
        slot["energy_kwh"] * slot["price_eur_per_mwh"] / 1000
        for slot in normal_slots
    )

    v2g_energy = 0.0
    v2g_reward = 0.0
    if mode == "normal":
        selected_slots = normal_slots
    else:
        required_charge = energy_needed
        if mode == "v2g":
            v2g_energy = min(vehicle.battery_capacity * 0.05, slot_capacity)
            required_charge += v2g_energy
        selected_slots = allocate_contiguous(
            candidate_slots,
            required_charge,
            variant,
            leave_export_slot=mode == "v2g",
        )

    if mode == "v2g":
        used_timestamps = {slot["timestamp"] for slot in selected_slots}
        charge_end = max(slot["timestamp"] for slot in selected_slots) + timedelta(minutes=15)
        discharge_candidates = [
            slot
            for slot in candidate_slots
            if slot["timestamp"] not in used_timestamps and slot["timestamp"] >= charge_end
        ]
        if not discharge_candidates:
            raise ValueError("No free time slot is available for V2G discharge.")
        peak_slot = max(discharge_candidates, key=lambda slot: slot["score"])
        v2g_reward = max(peak_slot["price"], 0) * v2g_energy / 1000
        selected_slots.append(
            {
                "timestamp": peak_slot["timestamp"],
                "action": "discharge",
                "energy_kwh": round(-v2g_energy, 4),
                "power_kw": round(-v2g_energy / SLOT_DURATION_HOURS, 4),
                "price_eur_per_mwh": round(peak_slot["price"], 4),
            }
        )

    selected_slots.sort(key=lambda slot: slot["timestamp"])
    charging_cost = sum(
        slot["energy_kwh"] * slot["price_eur_per_mwh"] / 1000
        for slot in selected_slots
        if slot["action"] == "charge"
    )
    net_cost = charging_cost - v2g_reward

    return {
        "mode": mode,
        "variant": "balanced" if mode == "normal" else variant,
        "energy_needed": round(energy_needed, 4),
        "predicted_duration": round(energy_needed / station.power_kw, 4),
        "cost": round(charging_cost, 4),
        "net_cost": round(net_cost, 4),
        "saving": round(normal_cost - net_cost, 4),
        "v2g_energy": round(v2g_energy, 4),
        "v2g_reward": round(v2g_reward, 4),
        "forecast_source": "machine_learning" if forecast_rows else "historical_baseline",
        "model_name": forecast_model_name or "daily-profile-baseline-v1",
        "start_time": min(slot["timestamp"] for slot in selected_slots),
        "end_time": max(slot["timestamp"] for slot in selected_slots)
        + timedelta(minutes=15),
        "slots": selected_slots,
    }
