ALTER TABLE energy_data
ADD COLUMN IF NOT EXISTS temperature_2m DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS cloud_cover DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS shortwave_radiation DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS wind_speed_100m DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS precipitation DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS station_availability_observations (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES stations(id),
    observed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_chargers INTEGER NOT NULL,
    available_chargers INTEGER NOT NULL,
    operational_status VARCHAR(20) NOT NULL,
    source VARCHAR(20) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_station_availability_station_time
ON station_availability_observations (station_id, observed_at);
