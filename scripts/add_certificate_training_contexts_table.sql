-- Certificate training context (Group 2) — idempotent for MySQL 8+

SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_training_contexts'
);

SET @sql := IF(
    @table_exists = 0,
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
        signatory_override JSON NULL,
        created_by BIGINT NOT NULL,
        updated_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL,
        PRIMARY KEY (id),
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
