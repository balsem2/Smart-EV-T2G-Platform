CREATE TABLE IF NOT EXISTS v2g_offers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    current_soc DOUBLE PRECISION NOT NULL,
    minimum_soc DOUBLE PRECISION NOT NULL,
    export_energy_kwh DOUBLE PRECISION NOT NULL,
    reward_eur DOUBLE PRECISION NOT NULL,
    export_start TIMESTAMP NOT NULL,
    export_end TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'offered',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
