-- Allow walk-in guests on certificate_participants (event / training calendar flow)
-- Idempotent for MySQL 8+

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
        MODIFY COLUMN user_id BIGINT NULL COMMENT ''users.id when linked; NULL for walk-in guests'',
        ADD COLUMN full_name VARCHAR(255) NULL COMMENT ''Guest name without salutation prefix'' AFTER user_id,
        ADD COLUMN salutation_id BIGINT NULL COMMENT ''Salutation for walk-in guests'' AFTER full_name,
        ADD COLUMN event_participant_id BIGINT NULL COMMENT ''Optional link to event_participants.id'' AFTER salutation_id',
    'SELECT ''certificate_participants guest columns already exist'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

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
