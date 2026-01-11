-- Add a unique constraint to ensure only one primary device per user
-- MySQL/MariaDB doesn't support partial unique indexes directly,
-- so we'll use a trigger-based approach

-- First, create a unique index on a computed column approach
-- Since MySQL doesn't support filtered indexes, we'll use a trigger

DELIMITER $$

-- Drop trigger if it exists
DROP TRIGGER IF EXISTS check_single_primary_device_before_insert$$

-- Create trigger to prevent multiple primary devices on INSERT
CREATE TRIGGER check_single_primary_device_before_insert
BEFORE INSERT ON user_devices
FOR EACH ROW
BEGIN
    IF NEW.is_primary = 1 AND NEW.is_active = 1 THEN
        -- Check if there's already a primary device for this user
        IF EXISTS (
            SELECT 1 FROM user_devices 
            WHERE user_id = NEW.user_id 
              AND is_primary = 1 
              AND is_active = 1
              AND id != NEW.id
        ) THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Only one primary device allowed per user';
        END IF;
    END IF;
END$$

-- Drop trigger if it exists
DROP TRIGGER IF EXISTS check_single_primary_device_before_update$$

-- Create trigger to prevent multiple primary devices on UPDATE
CREATE TRIGGER check_single_primary_device_before_update
BEFORE UPDATE ON user_devices
FOR EACH ROW
BEGIN
    IF NEW.is_primary = 1 AND NEW.is_active = 1 THEN
        -- Check if there's already a primary device for this user (excluding current row)
        IF EXISTS (
            SELECT 1 FROM user_devices 
            WHERE user_id = NEW.user_id 
              AND is_primary = 1 
              AND is_active = 1
              AND id != NEW.id
        ) THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Only one primary device allowed per user';
        END IF;
    END IF;
END$$

DELIMITER ;

-- Verify triggers were created
SHOW TRIGGERS LIKE 'user_devices';

