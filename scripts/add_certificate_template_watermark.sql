-- Optional distributed/center watermark on certificate templates
-- Usage: mysql -u <user> -p <database> < scripts/add_certificate_template_watermark.sql

SET @col_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_templates'
      AND COLUMN_NAME = 'watermark_logo_url'
);

SET @sql := IF(
    @col_exists = 0,
    'ALTER TABLE certificate_templates
        ADD COLUMN watermark_logo_url VARCHAR(500) NULL
            COMMENT ''Public URL to watermark PNG (tiled or centered)''
            AFTER background_filename,
        ADD COLUMN watermark_logo_filename VARCHAR(255) NULL
            AFTER watermark_logo_url,
        ADD COLUMN watermark_opacity DECIMAL(4, 3) NOT NULL DEFAULT 0.120
            COMMENT ''0.05–0.30 typical''
            AFTER watermark_logo_filename,
        ADD COLUMN watermark_style VARCHAR(20) NOT NULL DEFAULT ''distributed''
            COMMENT ''distributed or center''
            AFTER watermark_opacity,
        ADD COLUMN watermark_enabled TINYINT(1) NOT NULL DEFAULT 0
            AFTER watermark_style',
    'SELECT ''certificate_templates watermark columns already exist'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
