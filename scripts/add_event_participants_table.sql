-- Training calendar event participants — idempotent for MySQL 8+
-- Walk-in guests and linked system users for events (training calendar).

SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'event_participants'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE event_participants (
        id BIGINT NOT NULL AUTO_INCREMENT,
        event_id BIGINT NOT NULL,
        user_id BIGINT NULL COMMENT ''users.id when linked; NULL for walk-in guests'',
        full_name VARCHAR(255) NULL COMMENT ''Guest name without salutation prefix'',
        salutation_id BIGINT NULL COMMENT ''Salutation for walk-in guests'',
        organization VARCHAR(255) NULL,
        email VARCHAR(255) NULL,
        phone VARCHAR(50) NULL,
        notes TEXT NULL,
        created_by BIGINT NOT NULL,
        updated_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL,
        PRIMARY KEY (id),
        INDEX idx_event_participants_event (event_id),
        INDEX idx_event_participants_user (user_id),
        INDEX idx_event_participants_salutation (salutation_id),
        INDEX idx_event_participants_deleted (deleted_at),
        CONSTRAINT fk_event_participants_event
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''event_participants already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Event participants table migration complete' AS message;
