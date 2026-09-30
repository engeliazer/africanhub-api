-- Books / LMS integration tables (reading entitlement + grant audit log)
-- Idempotent for MySQL 8+ — safe to run more than once on production.
-- Alembic equivalent: fl4d5e6f7a8b_add_books_tables.py
--
-- Prerequisites: tables `users`, `subjects` must exist.
--
-- Usage:
--   mysql -u USER -p DB_NAME < scripts/add_books_lms_tables.sql

-- ---------------------------------------------------------------------------
-- book_subject_links
-- ---------------------------------------------------------------------------
SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'book_subject_links'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE book_subject_links (
        id BIGINT NOT NULL AUTO_INCREMENT,
        lms_book_id INT NOT NULL COMMENT ''Numeric LMS book id'',
        subject_id BIGINT NOT NULL,
        title VARCHAR(500) NULL,
        description TEXT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_by BIGINT NOT NULL,
        updated_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uq_book_subject_link (lms_book_id, subject_id),
        INDEX ix_book_subject_links_id (id),
        INDEX idx_book_subject_links_lms_book (lms_book_id),
        INDEX idx_book_subject_links_subject (subject_id),
        INDEX idx_book_subject_links_active (is_active),
        INDEX idx_book_subject_links_deleted (deleted_at),
        CONSTRAINT fk_book_subject_links_subject
            FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
        CONSTRAINT fk_book_subject_links_created_by
            FOREIGN KEY (created_by) REFERENCES users (id),
        CONSTRAINT fk_book_subject_links_updated_by
            FOREIGN KEY (updated_by) REFERENCES users (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''book_subject_links already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- book_access_grant_logs
-- ---------------------------------------------------------------------------
SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'book_access_grant_logs'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE book_access_grant_logs (
        id BIGINT NOT NULL AUTO_INCREMENT,
        user_id BIGINT NOT NULL,
        lms_book_id INT NOT NULL,
        lms_grant_id INT NULL,
        status VARCHAR(50) NOT NULL DEFAULT ''active'',
        issued_at DATETIME NULL,
        expires_at DATETIME NULL,
        revoked_at DATETIME NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        INDEX ix_book_access_grant_logs_id (id),
        INDEX idx_book_access_grant_logs_user (user_id),
        INDEX idx_book_access_grant_logs_book (lms_book_id),
        INDEX idx_book_access_grant_logs_grant (lms_grant_id),
        INDEX idx_book_access_grant_logs_status (status),
        CONSTRAINT fk_book_access_grant_logs_user
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''book_access_grant_logs already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Books LMS tables migration complete' AS message;
