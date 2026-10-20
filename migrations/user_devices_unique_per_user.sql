-- Same visitor_id allowed on different users. Unique only on (user_id, visitor_id).
-- Run on production MySQL (one time). Check indexes first:
--   SHOW INDEX FROM user_devices WHERE Column_name = 'visitor_id';

-- Drop global unique on visitor_id (MySQL index name is usually `visitor_id`)
ALTER TABLE user_devices DROP INDEX visitor_id;

-- If the above errors, try instead:
-- ALTER TABLE user_devices DROP INDEX uq_user_devices_visitor_id;

-- Composite unique per user
ALTER TABLE user_devices
  ADD UNIQUE KEY uq_user_devices_user_id_visitor_id (user_id, visitor_id);
