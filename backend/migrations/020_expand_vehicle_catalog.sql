BEGIN;

-- European-market battery variants are kept as separate catalogue entries so
-- charge duration and cost estimates use the correct capacity. V2G remains
-- disabled until a vehicle/station combination is explicitly validated.
INSERT INTO vehicle_catalog
    (model, battery_capacity, connector_types, supports_v2g, active)
VALUES
    ('Hyundai IONIQ 5 Standard Range (63 kWh)', 63.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Hyundai IONIQ 5 Long Range (84 kWh)', 84.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Hyundai IONIQ 6 Standard Range (53 kWh)', 53.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Hyundai IONIQ 6 Long Range (77.4 kWh)', 77.4, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Hyundai KONA Electric Standard Range (48.4 kWh)', 48.4, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Hyundai KONA Electric Long Range (65.4 kWh)', 65.4, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Kia EV3 Standard Range (58.3 kWh)', 58.3, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Kia EV3 Long Range (81.4 kWh)', 81.4, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Renault Megane E-Tech EV60 (60 kWh)', 60.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Volkswagen ID.3 Pure (52 kWh)', 52.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Volkswagen ID.3 Pro (59 kWh)', 59.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Volkswagen ID.3 GTX (79 kWh)', 79.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Volkswagen ID.4 Pure (52 kWh)', 52.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Volkswagen ID.4 Pro (77 kWh)', 77.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Volvo EX30 Single Motor (51 kWh)', 51.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE),
    ('Volvo EX30 Extended Range (69 kWh)', 69.0, 'Type 2 AC,CCS2 DC', FALSE, TRUE)
ON CONFLICT (model) DO UPDATE SET
    battery_capacity = EXCLUDED.battery_capacity,
    connector_types = EXCLUDED.connector_types,
    supports_v2g = EXCLUDED.supports_v2g,
    active = TRUE;

COMMIT;
