-- Issued certificates (Group 4) — idempotent for MySQL 8+

SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificates'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE certificates (
        id BIGINT NOT NULL AUTO_INCREMENT,
        training_context_id BIGINT NOT NULL,
        participant_id BIGINT NOT NULL,
        training_id BIGINT NOT NULL COMMENT ''Denormalized courses.id, subjects.id, or events.id'',
        cert_number VARCHAR(255) NOT NULL,
        qualifies_for_cpd TINYINT(1) NOT NULL DEFAULT 0,
        pdf_url VARCHAR(500) NOT NULL,
        issued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_by BIGINT NOT NULL,
        updated_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uq_certificates_cert_number (cert_number),
        INDEX idx_certificates_context (training_context_id),
        INDEX idx_certificates_participant (participant_id),
        INDEX idx_certificates_training (training_id),
        INDEX idx_certificates_deleted (deleted_at),
        CONSTRAINT fk_certificates_context
            FOREIGN KEY (training_context_id) REFERENCES certificate_training_contexts (id) ON DELETE CASCADE,
        CONSTRAINT fk_certificates_participant
            FOREIGN KEY (participant_id) REFERENCES certificate_participants (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''certificates already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Certificates table migration complete' AS message;
