ALTER TABLE charging_requests
ADD COLUMN IF NOT EXISTS station_id INTEGER REFERENCES stations(id);
