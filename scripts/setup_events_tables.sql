-- =============================================================================
-- Events API — full database setup (idempotent / safe to re-run)
-- Database: africanhub
--
-- Run:
--   mysql -u YOUR_USER -p africanhub < scripts/setup_events_tables.sql
--
-- Or paste into phpMyAdmin SQL tab (select africanhub database first).
-- =============================================================================

USE africanhub;

-- -----------------------------------------------------------------------------
-- Helper: add column only if it does not exist
-- -----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS add_column_if_missing;
DELIMITER //
CREATE PROCEDURE add_column_if_missing(
  IN p_table VARCHAR(64),
  IN p_column VARCHAR(64),
  IN p_definition TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table
      AND COLUMN_NAME = p_column
  ) THEN
    SET @sql = CONCAT('ALTER TABLE `', p_table, '` ADD COLUMN `', p_column, '` ', p_definition);
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END //
DELIMITER ;

-- -----------------------------------------------------------------------------
-- 1) invitation_trainers (required for event trainers — skip if already exists)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `invitation_trainers` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `full_name` VARCHAR(255) NOT NULL,
  `designation` VARCHAR(255) NULL,
  `bio` TEXT NULL,
  `qualifications` TEXT NULL,
  `photo` VARCHAR(500) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_by` BIGINT NULL,
  `updated_by` BIGINT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_invitation_trainers_id` (`id`),
  KEY `ix_invitation_trainers_full_name` (`full_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2) events — create if missing, then add any missing columns
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `events` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(255) NOT NULL,
  `course_title` VARCHAR(500) NOT NULL,
  `course_description` TEXT NULL,
  `venue` VARCHAR(500) NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  `start_time` TIME NULL,
  `end_time` TIME NULL,
  `learning_outcomes` TEXT NULL,
  `course_fee` DECIMAL(12, 2) NULL,
  `deposit_amount` DECIMAL(12, 2) NULL,
  `reservation_deadline` DATE NULL,
  `bank_account_name` VARCHAR(255) NULL,
  `bank_account_number` VARCHAR(100) NULL,
  `bank_name` VARCHAR(255) NULL,
  `is_published` TINYINT(1) NOT NULL DEFAULT 0,
  `invitation_template_path` VARCHAR(500) NULL,
  `invitation_template_filename` VARCHAR(255) NULL,
  `created_by` BIGINT NULL,
  `updated_by` BIGINT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_events_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- If events was created earlier without payment columns, add them now:
CALL add_column_if_missing('events', 'course_fee',           'DECIMAL(12, 2) NULL AFTER `learning_outcomes`');
CALL add_column_if_missing('events', 'deposit_amount',     'DECIMAL(12, 2) NULL AFTER `course_fee`');
CALL add_column_if_missing('events', 'reservation_deadline','DATE NULL AFTER `deposit_amount`');
CALL add_column_if_missing('events', 'bank_account_name',  'VARCHAR(255) NULL AFTER `reservation_deadline`');
CALL add_column_if_missing('events', 'bank_account_number','VARCHAR(100) NULL AFTER `bank_account_name`');
CALL add_column_if_missing('events', 'bank_name',          'VARCHAR(255) NULL AFTER `bank_account_number`');

-- -----------------------------------------------------------------------------
-- 3) event_trainer_assignments — links events to invitation_trainers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `event_trainer_assignments` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `event_id` BIGINT NOT NULL,
  `trainer_id` BIGINT NOT NULL,
  `display_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_event_trainer_assignments_id` (`id`),
  KEY `ix_event_trainer_assignments_event_id` (`event_id`),
  KEY `ix_event_trainer_assignments_trainer_id` (`trainer_id`),
  CONSTRAINT `fk_event_trainer_assignments_event_id`
    FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_event_trainer_assignments_trainer_id`
    FOREIGN KEY (`trainer_id`) REFERENCES `invitation_trainers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4) event_letter_requests — audit log for public PDF downloads
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `event_letter_requests` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `event_id` BIGINT NOT NULL,
  `first_name` VARCHAR(100) NOT NULL,
  `middle_name` VARCHAR(100) NULL,
  `last_name` VARCHAR(100) NOT NULL,
  `salutation_id` BIGINT NOT NULL,
  `organization` VARCHAR(255) NOT NULL,
  `address` TEXT NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `phone` VARCHAR(50) NOT NULL,
  `phone_verification_code` VARCHAR(6) NULL,
  `email_verification_code` VARCHAR(6) NULL,
  `phone_verified` TINYINT(1) NOT NULL DEFAULT 0,
  `email_verified` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_event_letter_requests_event_phone` (`event_id`, `phone`),
  UNIQUE KEY `uq_event_letter_requests_event_email` (`event_id`, `email`),
  KEY `ix_event_letter_requests_id` (`id`),
  KEY `ix_event_letter_requests_event_id` (`event_id`),
  KEY `ix_event_letter_requests_salutation_id` (`salutation_id`),
  CONSTRAINT `fk_event_letter_requests_event_id`
    FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_event_letter_requests_salutation_id`
    FOREIGN KEY (`salutation_id`) REFERENCES `salutations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Cleanup helper procedure
DROP PROCEDURE IF EXISTS add_column_if_missing;

-- Done
SELECT 'Events tables setup complete.' AS message;
