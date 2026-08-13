-- Unique certificate serial on certificate_participants (context pattern + participant id)
-- Idempotent for MySQL 8+

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
            COMMENT ''Unique serial: home/invited/training_code/certificate_participant_id''
            AFTER confirmation_status',
    'SELECT ''certificate_participants.serial_no already exists'' AS message'
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

SELECT 'certificate_participants serial_no migration complete' AS message;
