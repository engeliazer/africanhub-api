-- Create invitation_trainers table (required before event trainers work)
-- Run: mysql -u USER -p africanhub < scripts/create_invitation_trainers_table.sql

USE africanhub;

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

-- If event_trainer_assignments exists without FK to invitation_trainers, add it:
SET @fk_exists = (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND TABLE_NAME = 'event_trainer_assignments'
    AND CONSTRAINT_NAME = 'fk_event_trainer_assignments_trainer_id'
);

SET @assignments_exists = (
  SELECT COUNT(*)
  FROM information_schema.TABLES
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'event_trainer_assignments'
);

SET @trainers_exists = (
  SELECT COUNT(*)
  FROM information_schema.TABLES
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'invitation_trainers'
);

SET @sql = IF(
  @fk_exists = 0 AND @assignments_exists > 0 AND @trainers_exists > 0,
  'ALTER TABLE `event_trainer_assignments`
     ADD CONSTRAINT `fk_event_trainer_assignments_trainer_id`
     FOREIGN KEY (`trainer_id`) REFERENCES `invitation_trainers` (`id`) ON DELETE CASCADE',
  'SELECT ''FK already exists or prerequisites missing'' AS note'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'invitation_trainers table ready.' AS message;
