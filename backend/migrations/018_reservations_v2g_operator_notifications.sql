BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'driver';
ALTER TABLE users ADD COLUMN IF NOT EXISTS managed_station_id INTEGER REFERENCES stations(id);
ALTER TABLE vehicle_catalog ADD COLUMN IF NOT EXISTS supports_v2g BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS supports_v2g BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE stations ADD COLUMN IF NOT EXISTS supports_v2g BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE v2g_offers ADD COLUMN IF NOT EXISTS station_id INTEGER REFERENCES stations(id);

-- Academic demo capability flags. They are controlled project data, not a claim of
-- certification for every real-world trim or charging site.
UPDATE vehicle_catalog
SET supports_v2g = TRUE
WHERE id = (SELECT id FROM vehicle_catalog WHERE active = TRUE ORDER BY id LIMIT 1);

UPDATE vehicles v
SET supports_v2g = c.supports_v2g
FROM vehicle_catalog c
WHERE v.catalog_id = c.id;

UPDATE stations
SET supports_v2g = TRUE
WHERE id IN (
    SELECT id FROM stations
    WHERE active = TRUE AND operational_status = 'online'
    ORDER BY id LIMIT 3
);

UPDATE v2g_offers
SET station_id = (SELECT id FROM stations WHERE supports_v2g = TRUE ORDER BY id LIMIT 1)
WHERE station_id IS NULL;

ALTER TABLE v2g_offers ALTER COLUMN station_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS reservations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    station_id INTEGER NOT NULL REFERENCES stations(id),
    schedule_id INTEGER NOT NULL UNIQUE REFERENCES charging_schedule(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reservations_station_time
ON reservations(station_id, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_reservations_user ON reservations(user_id);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type VARCHAR(30) NOT NULL DEFAULT 'info',
    title VARCHAR(120) NOT NULL,
    message VARCHAR(500) NOT NULL,
    related_entity_type VARCHAR(30),
    related_entity_id INTEGER,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created
ON notifications(user_id, created_at DESC);

COMMIT;
