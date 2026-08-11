-- Events API tables for africanhub database
-- Run: mysql -u USER -p africanhub < scripts/create_events_tables.sql

USE africanhub;

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

CREATE TABLE IF NOT EXISTS `event_letter_requests` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `event_id` BIGINT NOT NULL,
  `full_name` VARCHAR(255) NOT NULL,
  `organization` VARCHAR(255) NOT NULL,
  `address` TEXT NOT NULL,
  `email` VARCHAR(255) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_event_letter_requests_id` (`id`),
  KEY `ix_event_letter_requests_event_id` (`event_id`),
  CONSTRAINT `fk_event_letter_requests_event_id`
    FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
