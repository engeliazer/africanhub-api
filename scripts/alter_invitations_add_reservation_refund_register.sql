-- Add Reservation, Refund Policy and How to Register fields to invitations
-- Safe to re-run. Equivalent to alembic revision fw5c6d7e8f9a.
-- Run: mysql -u USER -p africanhub < scripts/alter_invitations_add_reservation_refund_register.sql

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

CALL add_column_if_missing('invitations', 'reservation_details', 'TEXT NULL AFTER `payment_intro`');
CALL add_column_if_missing('invitations', 'refund_policy',       'TEXT NULL AFTER `reservation_details`');
CALL add_column_if_missing('invitations', 'how_to_register',     'TEXT NULL AFTER `refund_policy`');

DROP PROCEDURE IF EXISTS add_column_if_missing;

SELECT 'Invitations reservation/refund/register upgrade complete.' AS message;
