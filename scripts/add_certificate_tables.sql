-- Certificate module tables (Groups 1 & 2) — idempotent for MySQL 8+
-- Creates:
--   1. certificate_templates
--   2. certificate_template_signatories
--   3. certificate_training_contexts
--
-- Usage:
--   mysql -u <user> -p <database_name> < scripts/add_certificate_tables.sql

-- ---------------------------------------------------------------------------
-- 1. certificate_templates (Group 1 — admin template + background)
-- ---------------------------------------------------------------------------
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
        INDEX idx_certificate_templates_deleted (deleted_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''certificate_templates already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- 2. certificate_template_signatories (Group 1 — signatory names + signatures)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 3. certificate_training_contexts (Group 2 — course/subject certificate run)
-- ---------------------------------------------------------------------------
SET @contexts_table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_training_contexts'
);

SET @sql := IF(
    @contexts_table_exists = 0,
    'CREATE TABLE certificate_training_contexts (
        id BIGINT NOT NULL AUTO_INCREMENT,
        training_type VARCHAR(20) NOT NULL COMMENT ''course or subject'',
        training_id BIGINT NOT NULL COMMENT ''courses.id or subjects.id'',
        certificate_template_id BIGINT NOT NULL,
        host_mode VARCHAR(20) NOT NULL DEFAULT ''single'' COMMENT ''single or collaboration'',
        host_organization_name VARCHAR(255) NOT NULL,
        invited_organization_name VARCHAR(255) NULL,
        home_logo_url VARCHAR(500) NULL,
        invited_logo_url VARCHAR(500) NULL,
        subject_title VARCHAR(500) NOT NULL,
        venue_text VARCHAR(500) NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        cpd_hours INT NOT NULL DEFAULT 0,
        cert_number_pattern VARCHAR(255) NOT NULL,
        home_code VARCHAR(50) NOT NULL,
        invited_code VARCHAR(50) NULL,
        signatory_override JSON NULL COMMENT ''Optional per-run signatory override'',
        created_by BIGINT NOT NULL,
        updated_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL,
        PRIMARY KEY (id),
        INDEX ix_certificate_training_contexts_id (id),
        INDEX idx_certificate_training_contexts_training (training_type, training_id),
        INDEX idx_certificate_training_contexts_template (certificate_template_id),
        INDEX idx_certificate_training_contexts_deleted (deleted_at),
        CONSTRAINT fk_certificate_training_contexts_template
            FOREIGN KEY (certificate_template_id) REFERENCES certificate_templates (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''certificate_training_contexts already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Certificate tables migration complete' AS message;
