-- Add salutation_id to users + link certificate participants to users
-- Idempotent for MySQL 8+

SET @col_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'users'
      AND COLUMN_NAME = 'salutation_id'
);

SET @sql := IF(
    @col_exists = 0,
    'ALTER TABLE users ADD COLUMN salutation_id BIGINT NULL COMMENT ''FK to salutations.id'' AFTER is_admin',
    'SELECT ''users.salutation_id already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'users'
      AND INDEX_NAME = 'idx_users_salutation_id'
);

SET @sql := IF(
    @idx_exists = 0,
    'ALTER TABLE users ADD INDEX idx_users_salutation_id (salutation_id)',
    'SELECT ''idx_users_salutation_id already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- certificate_participants: migrate to user_id if old columns exist
SET @has_user_id := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'user_id'
);

SET @has_full_name := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'full_name'
);

SET @sql := IF(
    @has_user_id = 0 AND @has_full_name > 0,
    'ALTER TABLE certificate_participants
        ADD COLUMN user_id BIGINT NULL AFTER training_context_id',
    'SELECT ''skip add user_id'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @has_user_id = 0 AND @has_full_name > 0,
    'ALTER TABLE certificate_participants
        DROP FOREIGN KEY fk_certificate_participants_salutation',
    'SELECT ''skip drop salutation fk'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @has_full_name > 0,
    'ALTER TABLE certificate_participants
        DROP COLUMN full_name,
        DROP COLUMN salutation_id',
    'SELECT ''skip drop old participant columns'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_user_id := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND COLUMN_NAME = 'user_id'
);

SET @sql := IF(
    @has_user_id > 0,
    'ALTER TABLE certificate_participants MODIFY COLUMN user_id BIGINT NOT NULL',
    'SELECT ''skip modify user_id'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
      AND INDEX_NAME = 'idx_certificate_participants_user'
);

SET @sql := IF(
    @idx_exists = 0 AND @has_user_id > 0,
    'ALTER TABLE certificate_participants ADD INDEX idx_certificate_participants_user (user_id)',
    'SELECT ''skip user index'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'users.salutation_id + certificate_participants.user_id migration complete' AS message;
