ALTER TABLE payments
ADD COLUMN IF NOT EXISTS original_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS points_redeemed INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS points_discount_eur DOUBLE PRECISION NOT NULL DEFAULT 0;

UPDATE payments
SET original_amount = amount
WHERE original_amount = 0;

ALTER TABLE payments DROP CONSTRAINT IF EXISTS ck_payments_points_redemption;
ALTER TABLE payments ADD CONSTRAINT ck_payments_points_redemption CHECK (
    points_redeemed >= 0
    AND MOD(points_redeemed, 100) = 0
    AND points_discount_eur >= 0
    AND amount >= 0
    AND original_amount >= amount
);
