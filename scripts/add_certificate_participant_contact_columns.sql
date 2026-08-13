-- email + organization on certificate_participants — idempotent MySQL 8+

SET @has_email := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'email'
);

SET @sql := IF(
    @has_email = 0,
    'ALTER TABLE certificate_participants
        ADD COLUMN email VARCHAR(255) NULL AFTER event_participant_id,
        ADD COLUMN organization VARCHAR(255) NULL AFTER email',
    'SELECT ''certificate_participants email/organization already exist'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'certificate_participants contact columns migration complete' AS message;
