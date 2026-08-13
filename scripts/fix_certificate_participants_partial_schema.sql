-- Fix partial certificate_participants schema (full_name present, event_participant_id missing)
-- Idempotent for MySQL 8+

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
    'SELECT ''user_id already nullable'' AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

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
        ADD COLUMN event_participant_id BIGINT NULL
            COMMENT ''Optional link to event_participants.id''
            AFTER salutation_id',
    'SELECT ''event_participant_id already exists'' AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_serial_no := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'serial_no'
);

SET @sql := IF(
    @has_serial_no = 0,
    'ALTER TABLE certificate_participants
        ADD COLUMN serial_no VARCHAR(255) NULL
            COMMENT ''Unique serial from cert_number_pattern and participant id''
            AFTER confirmation_status',
    'SELECT ''serial_no already exists'' AS message'
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
    'ALTER TABLE certificate_participants
        ADD INDEX idx_certificate_participants_event_participant (event_participant_id)',
    'SELECT ''idx_certificate_participants_event_participant already exists'' AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND INDEX_NAME = 'uq_certificate_participants_serial_no'
);

SET @sql := IF(
    @idx_exists = 0,
    'ALTER TABLE certificate_participants
        ADD UNIQUE KEY uq_certificate_participants_serial_no (serial_no)',
    'SELECT ''uq_certificate_participants_serial_no already exists'' AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'certificate_participants partial schema fix complete' AS message;
