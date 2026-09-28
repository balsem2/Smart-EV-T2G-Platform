"""Create or refresh the local academic operator account."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import Station, User
from app.security import hash_password


EMAIL = "operator@smart-ev.at"
PASSWORD = "SmartEV-Operator-2026"


def main() -> None:
    with Session(get_engine()) as database_session:
        station = database_session.scalar(
            select(Station).where(Station.supports_v2g.is_(True)).order_by(Station.id)
        )
        if station is None:
            raise RuntimeError("Run migration 018 and configure at least one V2G station first.")
        user = database_session.scalar(
            select(User).where(User.email.in_([EMAIL, "operator@smart-ev.local"]))
        )
        if user is None:
            user = User(name="Smart EV Operator", email=EMAIL, password_hash=hash_password(PASSWORD))
            database_session.add(user)
        user.email = EMAIL
        user.role = "operator"
        user.managed_station_id = station.id
        user.onboarding_completed = True
        database_session.commit()
        print(f"Demo operator ready for station #{station.id}: {EMAIL}")


if __name__ == "__main__":
    main()
