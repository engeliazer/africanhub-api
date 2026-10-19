-- Allow the same visitor_id on different users; unique only per (user_id, visitor_id).
-- Run once on production if not using alembic upgrade.

ALTER TABLE user_devices DROP INDEX uq_user_devices_visitor_id;
-- If the above fails, try: ALTER TABLE user_devices DROP INDEX visitor_id;

ALTER TABLE user_devices
  ADD CONSTRAINT uq_user_devices_user_id_visitor_id UNIQUE (user_id, visitor_id);
