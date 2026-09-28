BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP;
UPDATE users SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL;

ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider VARCHAR(20) NOT NULL DEFAULT 'local_demo';
ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider_session_id VARCHAR(255);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS invoice_url VARCHAR(500);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS invoice_pdf VARCHAR(500);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_provider_session
ON payments(provider_session_id) WHERE provider_session_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS account_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose VARCHAR(30) NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_account_tokens_user_purpose
ON account_tokens(user_id, purpose, expires_at);

COMMIT;
