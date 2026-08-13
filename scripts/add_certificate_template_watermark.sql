-- Optional watermark columns on certificate_templates (idempotent — each column checked)
-- Matches production schema: watermark_logo_url, watermark_opacity, watermark_style
-- Optional extras: watermark_logo_filename, watermark_enabled
--
-- Usage: mysql -u <user> -p <database> < scripts/add_certificate_template_watermark.sql

-- watermark_logo_url
SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'certificate_templates'
      AND COLUMN_NAME = 'watermark_logo_url'
);
SET @sql := IF(@exists = 0,
    'ALTER TABLE certificate_templates ADD COLUMN watermark_logo_url VARCHAR(500) NULL AFTER background_filename',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- watermark_opacity
SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'certificate_templates'
      AND COLUMN_NAME = 'watermark_opacity'
);
SET @sql := IF(@exists = 0,
    'ALTER TABLE certificate_templates ADD COLUMN watermark_opacity DECIMAL(3,2) NOT NULL DEFAULT 0.12 AFTER watermark_logo_url',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- watermark_style
SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'certificate_templates'
      AND COLUMN_NAME = 'watermark_style'
);
SET @sql := IF(@exists = 0,
    'ALTER TABLE certificate_templates ADD COLUMN watermark_style VARCHAR(20) NOT NULL DEFAULT ''distributed'' AFTER watermark_opacity',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Optional: watermark_logo_filename (not required by the app)
SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'certificate_templates'
      AND COLUMN_NAME = 'watermark_logo_filename'
);
SET @sql := IF(@exists = 0,
    'ALTER TABLE certificate_templates ADD COLUMN watermark_logo_filename VARCHAR(255) NULL AFTER watermark_logo_url',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Optional: watermark_enabled (app infers from watermark_logo_url if absent)
SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'certificate_templates'
      AND COLUMN_NAME = 'watermark_enabled'
);
SET @sql := IF(@exists = 0,
    'ALTER TABLE certificate_templates ADD COLUMN watermark_enabled TINYINT(1) NOT NULL DEFAULT 0 AFTER watermark_style',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'certificate_templates watermark migration complete' AS message;
