-- Add optional details document URL to subjects (idempotent for MySQL 8+)
SET @col_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'subjects'
      AND COLUMN_NAME = 'details_document_url'
);

SET @sql := IF(
    @col_exists = 0,
    'ALTER TABLE subjects ADD COLUMN details_document_url VARCHAR(512) NULL COMMENT ''Public URL to subject details document (PDF/DOC/etc.)'' AFTER is_active',
    'SELECT ''details_document_url already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
