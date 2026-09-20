ALTER TABLE charging_schedule
ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'quoted';

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL UNIQUE REFERENCES charging_schedule(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    amount DOUBLE PRECISION NOT NULL CHECK (amount >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    payment_method VARCHAR(30) NOT NULL,
    card_last4 VARCHAR(4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'paid',
    reference VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments(user_id);
