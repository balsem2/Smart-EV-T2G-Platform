DO $$
BEGIN
    IF to_regclass('public.v2g_transactions') IS NOT NULL
       AND to_regclass('public.reward_events') IS NULL THEN
        ALTER TABLE v2g_transactions RENAME TO reward_events;
    END IF;
END $$;

ALTER TABLE reward_events
ADD COLUMN IF NOT EXISTS reward_type VARCHAR(20) NOT NULL DEFAULT 'v2g_export',
ADD COLUMN IF NOT EXISTS saving_eur DOUBLE PRECISION NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS points INTEGER NOT NULL DEFAULT 0;

UPDATE reward_events
SET points = FLOOR(GREATEST(COALESCE(energy_returned, 0), 0) * 10 + 0.5)::INTEGER
WHERE reward_type = 'v2g_export' AND points = 0;

ALTER TABLE reward_events DROP CONSTRAINT IF EXISTS ck_reward_events_type;
ALTER TABLE reward_events ADD CONSTRAINT ck_reward_events_type
CHECK (reward_type IN ('v1g_saving', 'v2g_export'));
