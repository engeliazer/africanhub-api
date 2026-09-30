-- Book purchase entitlements + order payment columns
-- Run after add_book_sales_tables.sql
-- Idempotent for MySQL 8+

-- Extend book_orders for payment workflow
SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'book_orders' AND COLUMN_NAME = 'payment_id'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE book_orders
        ADD COLUMN payment_id BIGINT NULL AFTER currency,
        ADD COLUMN attachment_path VARCHAR(500) NULL AFTER payment_id,
        ADD COLUMN attachment_filename VARCHAR(255) NULL AFTER attachment_path,
        ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at,
        ADD INDEX idx_book_orders_payment (payment_id),
        ADD CONSTRAINT fk_book_orders_payment FOREIGN KEY (payment_id) REFERENCES payments(id)',
    'SELECT ''book_orders payment columns already exist'' AS message');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Widen status column if needed
SET @sql := 'ALTER TABLE book_orders MODIFY COLUMN status VARCHAR(30) NOT NULL DEFAULT ''PENDING_PAYMENT''';
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- user_paid_book_editions
SET @table_exists := (
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_paid_book_editions'
);
SET @sql := IF(@table_exists = 0,
    'CREATE TABLE user_paid_book_editions (
        id BIGINT NOT NULL AUTO_INCREMENT,
        user_id BIGINT NOT NULL,
        book_reference_id VARCHAR(100) NOT NULL,
        edition_reference_id VARCHAR(100) NOT NULL,
        order_id BIGINT NOT NULL,
        payment_id BIGINT NOT NULL,
        paid_amount DECIMAL(12, 2) NOT NULL,
        currency VARCHAR(10) NOT NULL DEFAULT ''TZS'',
        paid_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_user_paid_edition (user_id, edition_reference_id),
        INDEX idx_user_paid_editions_user (user_id),
        INDEX idx_user_paid_editions_book (book_reference_id),
        INDEX idx_user_paid_editions_edition (edition_reference_id),
        CONSTRAINT fk_user_paid_editions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_user_paid_editions_order FOREIGN KEY (order_id) REFERENCES book_orders(id) ON DELETE CASCADE,
        CONSTRAINT fk_user_paid_editions_payment FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''user_paid_book_editions already exists'' AS message');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Optional: store LMS book ref as string in grant logs (UUID)
SET @col_type := (
    SELECT DATA_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'book_access_grant_logs' AND COLUMN_NAME = 'lms_book_id'
);
SET @sql := IF(@col_type = 'int',
    'ALTER TABLE book_access_grant_logs MODIFY COLUMN lms_book_id VARCHAR(100) NOT NULL',
    'SELECT ''book_access_grant_logs.lms_book_id already string'' AS message');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_type := (
    SELECT DATA_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'book_subject_links' AND COLUMN_NAME = 'lms_book_id'
);
SET @sql := IF(@col_type = 'int',
    'ALTER TABLE book_subject_links MODIFY COLUMN lms_book_id VARCHAR(100) NOT NULL',
    'SELECT ''book_subject_links.lms_book_id already string'' AS message');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'Book purchase entitlements migration complete' AS message;
