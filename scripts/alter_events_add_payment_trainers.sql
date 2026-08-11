-- Add payment fields and trainer assignments to events
-- Run: mysql -u USER -p africanhub < scripts/alter_events_add_payment_trainers.sql

USE africanhub;

ALTER TABLE `events`
  ADD COLUMN `course_fee` DECIMAL(12, 2) NULL AFTER `learning_outcomes`,
  ADD COLUMN `deposit_amount` DECIMAL(12, 2) NULL AFTER `course_fee`,
  ADD COLUMN `reservation_deadline` DATE NULL AFTER `deposit_amount`,
  ADD COLUMN `bank_account_name` VARCHAR(255) NULL AFTER `reservation_deadline`,
  ADD COLUMN `bank_account_number` VARCHAR(100) NULL AFTER `bank_account_name`,
  ADD COLUMN `bank_name` VARCHAR(255) NULL AFTER `bank_account_number`;

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
