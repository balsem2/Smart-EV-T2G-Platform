UPDATE stations
SET active = FALSE
WHERE active = TRUE;

INSERT INTO stations
    (station_name, city, latitude, longitude, charger_type, power_kw, operator, source, active)
VALUES
    ('BOE Apartment Hotel Singerstrasse', 'Wien', 48.206473, 16.375692, 'Type 2 AC', 11.1, 'SMATRICS GmbH und Co KG', 'E-Control:EAT5726095', TRUE),
    ('Graz Sparkassenplatz', 'Graz', 47.069652, 15.437908, 'Type 2 AC', 11, 'Energie Steiermark', 'E-Control:E72E21FE1645CDDDAF86C3B285BB0', TRUE),
    ('Raiffeisenverband Schallmoos', 'Salzburg', 47.809721, 13.054262, 'Type 2 AC', 11, 'Salzburg AG', 'E-Control:E9991777', TRUE),
    ('Tiefgarage Hauptplatz', 'Linz', 48.306627, 14.285100, 'Type 2 AC', 11, 'LINZ AG', 'E-Control:EF7EA3647C2B541E0A74021BA', TRUE),
    ('UNIQA OAMTC Landesdirektion Tirol', 'Innsbruck', 47.267169, 11.402046, 'Type 2 AC', 11, 'OAMTC Verbandsbetriebe GmbH', 'E-Control:E04C31C1556164A7D92A5A4EB', TRUE),
    ('STW eMobil Dr. Hermann Gasse 2', 'Klagenfurt', 46.624036, 14.305766, 'Type 2 AC', 22, 'Energie Klagenfurt GmbH', 'E-Control:E5178470', TRUE),
    ('Intern Kundenparkplatz', 'Eisenstadt', 47.844160, 16.522525, 'Type 2 AC', 11, 'ChargePoint Austria GmbH', 'E-Control:E5171278', TRUE),
    ('Parkplatz Rathausbezirk', 'Bregenz', 47.503108, 9.748350, 'Type 2 AC', 22, 'illwerke vkw AG', 'E-Control:ED0F581E5C48648C9AD18A1D7', TRUE),
    ('Tiefgarage Rathausplatz', 'St. Polten', 48.204770, 15.621564, 'Type 2 AC', 11, 'EVN Energieservices GmbH', 'E-Control:EC8A426699D4F4851929B3C53', TRUE)
ON CONFLICT (station_name, operator) DO UPDATE SET
    city = EXCLUDED.city,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    charger_type = EXCLUDED.charger_type,
    power_kw = EXCLUDED.power_kw,
    source = EXCLUDED.source,
    active = TRUE;
