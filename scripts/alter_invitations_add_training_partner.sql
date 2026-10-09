-- Add training partner fields to invitations
-- Existing invitations are set to DSM CPA Review Center so their letters stay unchanged.
-- Safe to re-run (the backfill only runs when has_training_partner is first added).
-- Equivalent to alembic revision fx6d7e8f9a0b.
-- Run: mysql -u USER -p africanhub < scripts/alter_invitations_add_training_partner.sql

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

SET @flag_missing = (
  SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'invitations' AND COLUMN_NAME = 'has_training_partner'
);

CALL add_column_if_missing('invitations', 'has_training_partner',  'TINYINT(1) NOT NULL DEFAULT 0 AFTER `how_to_register`');
CALL add_column_if_missing('invitations', 'partner_name',          'VARCHAR(255) NULL AFTER `has_training_partner`');
CALL add_column_if_missing('invitations', 'partner_logo_path',     'VARCHAR(500) NULL AFTER `partner_name`');
CALL add_column_if_missing('invitations', 'partner_logo_filename', 'VARCHAR(255) NULL AFTER `partner_logo_path`');

UPDATE `invitations`
SET `has_training_partner` = 1,
    `partner_name` = 'DSM CPA Review Center',
    `partner_logo_path` = 'storage/images/logoDcrc.jpg',
    `partner_logo_filename` = 'logoDcrc.jpg'
WHERE @flag_missing = 1;

DROP PROCEDURE IF EXISTS add_column_if_missing;

SELECT 'Invitations training partner upgrade complete.' AS message;
