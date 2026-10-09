-- Add "Why You Should Attend" fields to invitations
-- Safe to re-run. Equivalent to alembic revision fs1e2f3a4b5c.
-- Run: mysql -u USER -p africanhub < scripts/alter_invitations_add_why_attend.sql

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

CALL add_column_if_missing('invitations', 'why_attend_intro',  'TEXT NULL AFTER `learning_outcomes`');
CALL add_column_if_missing('invitations', 'why_attend_points', 'TEXT NULL AFTER `why_attend_intro`');

DROP PROCEDURE IF EXISTS add_column_if_missing;

SELECT 'Invitations why_attend upgrade complete.' AS message;
