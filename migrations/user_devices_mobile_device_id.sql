-- Hash of vendor id + android id, sent by the mobile app as device_id.
ALTER TABLE user_devices
  ADD COLUMN mobile_device_id VARCHAR(128) NULL AFTER visitor_id,
  ADD INDEX ix_user_devices_mobile_device_id (mobile_device_id);
