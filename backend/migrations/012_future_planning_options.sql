ALTER TABLE charging_requests
ADD COLUMN IF NOT EXISTS earliest_start_time TIMESTAMP;

ALTER TABLE charging_schedule
ADD COLUMN IF NOT EXISTS variant VARCHAR(20) NOT NULL DEFAULT 'balanced';

ALTER TABLE charging_schedule DROP CONSTRAINT IF EXISTS ck_charging_schedule_variant;
ALTER TABLE charging_schedule ADD CONSTRAINT ck_charging_schedule_variant
CHECK (variant IN ('balanced', 'lowest_cost', 'greenest'));
