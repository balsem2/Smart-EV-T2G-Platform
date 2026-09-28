ALTER TABLE vehicle_catalog
ADD COLUMN IF NOT EXISTS connector_types VARCHAR(120);

UPDATE vehicle_catalog
SET connector_types = CASE model
    WHEN 'BMW i3' THEN 'Type 2 AC,CCS2 DC'
    WHEN 'Chevy Bolt' THEN 'Type 1 AC,CCS1 DC'
    WHEN 'Hyundai Kona' THEN 'Type 2 AC,CCS2 DC'
    WHEN 'Nissan Leaf' THEN 'Type 2 AC,CHAdeMO DC'
    WHEN 'Tesla Model 3' THEN 'Type 2 AC,CCS2 DC'
    ELSE 'Type 2 AC'
END
WHERE connector_types IS NULL;

ALTER TABLE vehicle_catalog
ALTER COLUMN connector_types SET DEFAULT 'Type 2 AC',
ALTER COLUMN connector_types SET NOT NULL;

ALTER TABLE vehicles
ADD COLUMN IF NOT EXISTS connector_types VARCHAR(120);

UPDATE vehicles AS vehicle
SET connector_types = catalogue.connector_types
FROM vehicle_catalog AS catalogue
WHERE vehicle.catalog_id = catalogue.id
  AND vehicle.connector_types IS NULL;

UPDATE vehicles
SET connector_types = 'Type 2 AC'
WHERE connector_types IS NULL;
