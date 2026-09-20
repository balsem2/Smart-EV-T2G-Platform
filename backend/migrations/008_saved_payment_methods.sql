CREATE TABLE IF NOT EXISTS payment_methods (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    cardholder_name VARCHAR(100) NOT NULL,
    brand VARCHAR(20) NOT NULL,
    last4 VARCHAR(4) NOT NULL,
    expiry_month INTEGER NOT NULL CHECK (expiry_month BETWEEN 1 AND 12),
    expiry_year INTEGER NOT NULL,
    provider_token VARCHAR(80) NOT NULL UNIQUE,
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_payment_methods_user_id
ON payment_methods(user_id);
