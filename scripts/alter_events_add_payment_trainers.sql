-- Upgrade existing events table (payment + trainers)
-- Safe to re-run. Prefer scripts/setup_events_tables.sql for full setup.
-- Run: mysql -u USER -p africanhub < scripts/alter_events_add_payment_trainers.sql

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

CALL add_column_if_missing('events', 'course_fee',            'DECIMAL(12, 2) NULL AFTER `learning_outcomes`');
CALL add_column_if_missing('events', 'deposit_amount',      'DECIMAL(12, 2) NULL AFTER `course_fee`');
CALL add_column_if_missing('events', 'reservation_deadline','DATE NULL AFTER `deposit_amount`');
CALL add_column_if_missing('events', 'bank_account_name',   'VARCHAR(255) NULL AFTER `reservation_deadline`');
CALL add_column_if_missing('events', 'bank_account_number', 'VARCHAR(100) NULL AFTER `bank_account_name`');
CALL add_column_if_missing('events', 'bank_name',           'VARCHAR(255) NULL AFTER `bank_account_number`');

DROP PROCEDURE IF EXISTS add_column_if_missing;

CREATE TABLE IF NOT EXISTS `event_trainer_assignments` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `event_id` BIGINT NOT NULL,
  `trainer_id` BIGINT NOT NULL,
  `display_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_event_trainer_assignments_event_id` (`event_id`),
  KEY `ix_event_trainer_assignments_trainer_id` (`trainer_id`),
  CONSTRAINT `fk_event_trainer_assignments_event_id`
    FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_event_trainer_assignments_trainer_id`
    FOREIGN KEY (`trainer_id`) REFERENCES `invitation_trainers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'Events upgrade complete.' AS message;
