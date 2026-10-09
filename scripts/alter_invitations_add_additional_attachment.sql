-- Add additional PDF attachment (e.g. Course Contents) to invitations
-- Safe to re-run. Equivalent to alembic revision fy7e8f9a0b1c.
-- Run: mysql -u USER -p africanhub < scripts/alter_invitations_add_additional_attachment.sql

USE africanhub;

DROP PROCEDURE IF EXISTS add_column_if_missing;
DELIMITER //
CREATE PROCEDURE add_column_if_missing(
  IN p_table VARCHAR(64),
  IN p_column VARCHAR(64),
  IN p_definition TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table AND COLUMN_NAME = p_column
  ) THEN
    SET @sql = CONCAT('ALTER TABLE `', p_table, '` ADD COLUMN `', p_column, '` ', p_definition);
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END //
DELIMITER ;

CALL add_column_if_missing('invitations', 'additional_attachment_path',     'VARCHAR(500) NULL AFTER `partner_logo_filename`');
CALL add_column_if_missing('invitations', 'additional_attachment_filename', 'VARCHAR(255) NULL AFTER `additional_attachment_path`');

DROP PROCEDURE IF EXISTS add_column_if_missing;

SELECT 'Invitations additional attachment upgrade complete.' AS message;
