-- Certificate templates (Group 1) — idempotent for MySQL 8+
-- Creates: certificate_templates, certificate_template_signatories

SET @templates_table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_templates'
);

SET @sql := IF(
    @templates_table_exists = 0,
    'CREATE TABLE certificate_templates (
        id BIGINT NOT NULL AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL,
        description TEXT NULL,
        background_url VARCHAR(500) NOT NULL COMMENT ''Public URL to empty background PDF/PNG'',
        background_filename VARCHAR(255) NULL COMMENT ''Original uploaded filename'',
        certificate_title VARCHAR(255) NOT NULL DEFAULT ''Certificate of Participation'',
        participation_prefix VARCHAR(500) NOT NULL DEFAULT ''Participated in the training on'',
        venue_template VARCHAR(500) NOT NULL DEFAULT ''held at {venue}'',
        date_template VARCHAR(500) NOT NULL DEFAULT ''from {start_date} to {end_date}'',
        cpd_template VARCHAR(1000) NOT NULL DEFAULT ''from {start_date} to {end_date} and qualified for the award of {cpd_hours} hours of Continuing Professional Development'',
        field_layout JSON NULL COMMENT ''Coordinate/layout config for PDF overlay renderer'',
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_by BIGINT NOT NULL,
        updated_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL,
        PRIMARY KEY (id),
        INDEX ix_certificate_templates_id (id),
        INDEX idx_certificate_templates_active (is_active),
        INDEX idx_certificate_templates_deleted (deleted_at),
        CONSTRAINT fk_certificate_templates_created_by FOREIGN KEY (created_by) REFERENCES users (id),
        CONSTRAINT fk_certificate_templates_updated_by FOREIGN KEY (updated_by) REFERENCES users (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''certificate_templates already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @signatories_table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_template_signatories'
);

SET @sql := IF(
    @signatories_table_exists = 0,
    'CREATE TABLE certificate_template_signatories (
        id BIGINT NOT NULL AUTO_INCREMENT,
        template_id BIGINT NOT NULL,
        display_order INT NOT NULL DEFAULT 1,
        full_name VARCHAR(255) NOT NULL,
        title VARCHAR(255) NOT NULL,
        signature_url VARCHAR(500) NULL COMMENT ''Public URL to signatory signature PNG/JPG'',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        INDEX ix_certificate_template_signatories_id (id),
        INDEX idx_certificate_template_signatories_template (template_id),
        CONSTRAINT fk_certificate_template_signatories_template
            FOREIGN KEY (template_id) REFERENCES certificate_templates (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''certificate_template_signatories already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
