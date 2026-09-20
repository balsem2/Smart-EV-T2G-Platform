import argparse
import csv
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.database import get_engine
from app.models import EnergyData


COLUMNS = {
    "timestamp": "utc_timestamp",
    "electricity_price": "AT_price_day_ahead",
    "grid_load": "AT_load_actual_entsoe_transparency",
    "solar_generation": "AT_solar_generation_actual",
    "wind_generation": "AT_wind_onshore_generation_actual",
}
CHUNK_SIZE = 2_000


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import consistent Austrian energy data into PostgreSQL."
    )
    parser.add_argument("source", type=Path, help="Open Power System Data CSV file")
    parser.add_argument("--start", type=datetime.fromisoformat)
    parser.add_argument("--end", type=datetime.fromisoformat)
    return parser.parse_args()


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def iter_rows(
    source: Path,
    start: datetime | None,
    end: datetime | None,
) -> Iterator[dict[str, datetime | float]]:
    required_columns = set(COLUMNS.values())

    with source.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"Missing CSV columns: {sorted(missing_columns)}")

        for source_row in reader:
            timestamp = parse_timestamp(source_row[COLUMNS["timestamp"]])
            if start is not None and timestamp < start:
                continue
            if end is not None and timestamp >= end:
                continue

            raw_values = {
                target: source_row[source_name]
                for target, source_name in COLUMNS.items()
                if target != "timestamp"
            }
            if any(value == "" for value in raw_values.values()):
                continue

            values = {name: float(value) for name, value in raw_values.items()}
            if (
                values["grid_load"] < 0
                or values["solar_generation"] < 0
                or values["wind_generation"] < 0
            ):
                continue

            yield {"timestamp": timestamp, **values}


def import_rows(rows: Iterable[dict[str, datetime | float]]) -> int:
    imported = 0
    batch: list[dict[str, datetime | float]] = []
    with get_engine().begin() as connection:
        for row in rows:
            batch.append(row)
            if len(batch) >= CHUNK_SIZE:
                _upsert_batch(connection, batch)
                imported += len(batch)
                batch.clear()
        if batch:
            _upsert_batch(connection, batch)
            imported += len(batch)
    if imported == 0:
        raise ValueError("No valid rows matched the selected period.")
    return imported


def _upsert_batch(connection, batch: list[dict[str, datetime | float]]) -> None:
    statement = insert(EnergyData).values(batch)
    statement = statement.on_conflict_do_update(
        index_elements=[EnergyData.timestamp],
        set_={
            "electricity_price": statement.excluded.electricity_price,
            "grid_load": statement.excluded.grid_load,
            "solar_generation": statement.excluded.solar_generation,
            "wind_generation": statement.excluded.wind_generation,
        },
    )
    connection.execute(statement)


def main() -> None:
    arguments = parse_arguments()
    imported = import_rows(
        iter_rows(arguments.source, arguments.start, arguments.end)
    )
    print(f"Imported {imported} Austrian energy rows.")


if __name__ == "__main__":
    main()
