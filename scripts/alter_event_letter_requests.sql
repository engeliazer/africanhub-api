-- Expand event_letter_requests: split name, contact, salutation, verification (MySQL 8+ idempotent)
-- Run after salutations table is seeded (needs code = 'none')

-- 1) Add new columns (skip if present)
SET @has_first_name := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'event_letter_requests' AND COLUMN_NAME = 'first_name'
);
SET @sql := IF(
    @has_first_name = 0,
    'ALTER TABLE event_letter_requests
        ADD COLUMN first_name VARCHAR(100) NULL AFTER event_id,
        ADD COLUMN middle_name VARCHAR(100) NULL AFTER first_name,
        ADD COLUMN last_name VARCHAR(100) NULL AFTER middle_name,
        ADD COLUMN salutation_id BIGINT NULL AFTER last_name,
        ADD COLUMN phone VARCHAR(50) NULL AFTER email,
        ADD COLUMN phone_verification_code VARCHAR(10) NULL AFTER phone,
        ADD COLUMN email_verification_code VARCHAR(10) NULL AFTER phone_verification_code,
        ADD COLUMN phone_verification_status VARCHAR(20) NOT NULL DEFAULT ''pending'' AFTER email_verification_code,
        ADD COLUMN email_verification_status VARCHAR(20) NOT NULL DEFAULT ''pending'' AFTER phone_verification_status',
    'SELECT ''event_letter_requests name/contact columns already exist'' AS message'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2) Backfill from legacy full_name when column still exists
SET @has_full_name := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'event_letter_requests' AND COLUMN_NAME = 'full_name'
);
SET @sql := IF(
    @has_full_name > 0,
    'UPDATE event_letter_requests
        SET first_name = COALESCE(NULLIF(first_name, ''''), full_name),
            last_name = COALESCE(NULLIF(last_name, ''''), ''-'')
        WHERE first_name IS NULL OR first_name = ''''',
    'SELECT ''skip full_name backfill'' AS message'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE event_letter_requests elr
SET salutation_id = (SELECT id FROM salutations WHERE code = 'none' LIMIT 1)
WHERE salutation_id IS NULL;

UPDATE event_letter_requests
SET phone = CONCAT('legacy', id)
WHERE phone IS NULL OR phone = '';

UPDATE event_letter_requests
SET email = CONCAT('legacy-', id, '@placeholder.local')
WHERE email IS NULL OR email = '';

-- 3) Enforce NOT NULL
ALTER TABLE event_letter_requests
    MODIFY COLUMN first_name VARCHAR(100) NOT NULL,
    MODIFY COLUMN last_name VARCHAR(100) NOT NULL,
    MODIFY COLUMN salutation_id BIGINT NOT NULL,
    MODIFY COLUMN email VARCHAR(255) NOT NULL,
    MODIFY COLUMN phone VARCHAR(50) NOT NULL;

-- 4) Drop legacy full_name
SET @sql := IF(
    @has_full_name > 0,
    'ALTER TABLE event_letter_requests DROP COLUMN full_name',
    'SELECT ''full_name already dropped'' AS message'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 5) Indexes + FK
SET @has_phone_uq := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'event_letter_requests'
      AND INDEX_NAME = 'uq_event_letter_requests_event_phone'
);
SET @sql := IF(
    @has_phone_uq = 0,
    'ALTER TABLE event_letter_requests ADD UNIQUE KEY uq_event_letter_requests_event_phone (event_id, phone)',
    'SELECT ''phone unique index exists'' AS message'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_email_uq := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'event_letter_requests'
      AND INDEX_NAME = 'uq_event_letter_requests_event_email'
);
SET @sql := IF(
    @has_email_uq = 0,
    'ALTER TABLE event_letter_requests ADD UNIQUE KEY uq_event_letter_requests_event_email (event_id, email)',
    'SELECT ''email unique index exists'' AS message'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_salutation_idx := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'event_letter_requests'
      AND INDEX_NAME = 'ix_event_letter_requests_salutation_id'
);
SET @sql := IF(
    @has_salutation_idx = 0,
    'ALTER TABLE event_letter_requests ADD INDEX ix_event_letter_requests_salutation_id (salutation_id)',
    'SELECT ''salutation index exists'' AS message'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'event_letter_requests schema update complete' AS message;
