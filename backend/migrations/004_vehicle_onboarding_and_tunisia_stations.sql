ALTER TABLE users
ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS vehicle_catalog (
    id SERIAL PRIMARY KEY,
    model VARCHAR(100) NOT NULL UNIQUE,
    battery_capacity DOUBLE PRECISION NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO vehicle_catalog (model, battery_capacity)
VALUES
    ('BMW i3', 42.2),
    ('Chevy Bolt', 65.0),
    ('Hyundai Kona', 64.0),
    ('Nissan Leaf', 40.0),
    ('Tesla Model 3', 60.0)
ON CONFLICT (model) DO UPDATE SET
    battery_capacity = EXCLUDED.battery_capacity,
    active = TRUE;

ALTER TABLE vehicles
ADD COLUMN IF NOT EXISTS catalog_id INTEGER REFERENCES vehicle_catalog(id);

UPDATE vehicles AS vehicle
SET catalog_id = catalogue.id
FROM vehicle_catalog AS catalogue
WHERE vehicle.catalog_id IS NULL
  AND LOWER(vehicle.model) = LOWER(catalogue.model);

UPDATE users
SET onboarding_completed = TRUE
WHERE EXISTS (
    SELECT 1 FROM vehicles WHERE vehicles.user_id = users.id
);

ALTER TABLE stations
ADD COLUMN IF NOT EXISTS source VARCHAR(255),
ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;

UPDATE stations
SET active = FALSE,
    source = COALESCE(source, 'legacy-demo')
WHERE station_name = 'Tunis Smart Hub';

CREATE UNIQUE INDEX IF NOT EXISTS ux_stations_name_operator
ON stations (station_name, operator);

INSERT INTO stations
    (station_name, city, charger_type, power_kw, operator, source, active)
VALUES
    ('Bizerte RN11', 'Bizerte', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Jardins du Lac', 'Tunis', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Grombalia A1', 'Grombalia', 'Type 2 · DC/AC', 50, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Borjine A1', 'Borjine', 'Type 2 · DC', 50, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('El Jem A1', 'El Jem', 'Type 2 · DC', 50, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Sousse I', 'Sousse', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Hamet Jerid Tozeur', 'Tozeur', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Tataouine 1', 'Tataouine', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Le Kef', 'Le Kef', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Hammamet 1', 'Hammamet', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE),
    ('Djerba Houmet Essouk', 'Djerba', 'Type 2 · AC', 22, 'TotalEnergies Tunisie', 'totalenergies.tn', TRUE)
ON CONFLICT (station_name, operator) DO UPDATE SET
    city = EXCLUDED.city,
    charger_type = EXCLUDED.charger_type,
    power_kw = EXCLUDED.power_kw,
    source = EXCLUDED.source,
    active = TRUE;
