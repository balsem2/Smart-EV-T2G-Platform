ALTER TABLE stations
ADD COLUMN IF NOT EXISTS total_chargers INTEGER NOT NULL DEFAULT 4,
ADD COLUMN IF NOT EXISTS available_chargers INTEGER NOT NULL DEFAULT 4,
ADD COLUMN IF NOT EXISTS operational_status VARCHAR(20) NOT NULL DEFAULT 'online',
ADD COLUMN IF NOT EXISTS availability_source VARCHAR(20) NOT NULL DEFAULT 'simulated',
ADD COLUMN IF NOT EXISTS last_status_at TIMESTAMP;

UPDATE stations
SET total_chargers = CASE WHEN power_kw >= 22 THEN 6 ELSE 4 END,
    available_chargers = CASE WHEN power_kw >= 22 THEN 3 ELSE 2 END,
    operational_status = 'online',
    availability_source = 'simulated',
    last_status_at = CURRENT_TIMESTAMP
WHERE active = TRUE;

ALTER TABLE stations DROP CONSTRAINT IF EXISTS ck_station_charger_counts;
ALTER TABLE stations ADD CONSTRAINT ck_station_charger_counts CHECK (
    total_chargers >= 1
    AND available_chargers >= 0
    AND available_chargers <= total_chargers
);

ALTER TABLE stations DROP CONSTRAINT IF EXISTS ck_station_operational_status;
ALTER TABLE stations ADD CONSTRAINT ck_station_operational_status CHECK (
    operational_status IN ('online', 'offline', 'maintenance')
);
