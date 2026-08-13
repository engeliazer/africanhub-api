-- Allow walk-in guests on certificate_participants (event / training calendar flow)
-- Idempotent for MySQL 8+ — each change is applied independently (safe on partial schemas)

-- 1. user_id nullable (required for walk-in guests)
SET @user_id_nullable := (
    SELECT IS_NULLABLE
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'user_id'
);

SET @sql := IF(
    @user_id_nullable = 'NO',
    'ALTER TABLE certificate_participants
        MODIFY COLUMN user_id BIGINT NULL COMMENT ''users.id when linked; NULL for walk-in guests''',
    'SELECT ''certificate_participants.user_id already nullable'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. full_name
SET @has_full_name := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'full_name'
);

SET @sql := IF(
    @has_full_name = 0,
    'ALTER TABLE certificate_participants
        ADD COLUMN full_name VARCHAR(255) NULL COMMENT ''Guest name without salutation prefix'' AFTER user_id',
    'SELECT ''certificate_participants.full_name already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. salutation_id
SET @has_salutation_id := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'salutation_id'
);

SET @sql := IF(
    @has_salutation_id = 0,
    'ALTER TABLE certificate_participants
        ADD COLUMN salutation_id BIGINT NULL COMMENT ''Salutation for walk-in guests'' AFTER full_name',
    'SELECT ''certificate_participants.salutation_id already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4. event_participant_id
SET @has_event_participant_id := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'event_participant_id'
);

SET @sql := IF(
    @has_event_participant_id = 0,
    'ALTER TABLE certificate_participants
        ADD COLUMN event_participant_id BIGINT NULL COMMENT ''Optional link to event_participants.id'' AFTER salutation_id',
    'SELECT ''certificate_participants.event_participant_id already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. indexes
SET @idx_exists := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND INDEX_NAME = 'idx_certificate_participants_salutation'
);

SET @sql := IF(
    @idx_exists = 0,
    'ALTER TABLE certificate_participants ADD INDEX idx_certificate_participants_salutation (salutation_id)',
    'SELECT ''idx_certificate_participants_salutation already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND INDEX_NAME = 'idx_certificate_participants_event_participant'
);

SET @sql := IF(
    @idx_exists = 0,
    'ALTER TABLE certificate_participants ADD INDEX idx_certificate_participants_event_participant (event_participant_id)',
    'SELECT ''idx_certificate_participants_event_participant already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'certificate_participants guest columns migration complete' AS message;
