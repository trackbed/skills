ALTER TABLE accounts ADD COLUMN plan_id TEXT;

UPDATE accounts
SET plan_id = CASE legacy_plan
  WHEN 'basic' THEN 'plan_starter'
  WHEN 'plus' THEN 'plan_team'
  WHEN 'max' THEN 'plan_business'
END
WHERE plan_id IS NULL;
