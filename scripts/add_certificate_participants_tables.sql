-- Certificate participants (Group 3) + salutations lookup — idempotent for MySQL 8+
-- Run after scripts/add_certificate_tables.sql

-- ---------------------------------------------------------------------------
-- 1. salutations
-- ---------------------------------------------------------------------------
SET @salutations_table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'salutations'
);

SET @sql := IF(
    @salutations_table_exists = 0,
    'CREATE TABLE salutations (
        id BIGINT NOT NULL AUTO_INCREMENT,
        label VARCHAR(100) NOT NULL,
        code VARCHAR(50) NOT NULL,
        qualifies_for_cpd TINYINT(1) NOT NULL DEFAULT 0,
        display_order INT NOT NULL DEFAULT 0,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_salutations_label (label),
        UNIQUE KEY uq_salutations_code (code),
        INDEX idx_salutations_active (is_active),
        INDEX idx_salutations_display_order (display_order)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''salutations already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- 2. certificate_participants
-- ---------------------------------------------------------------------------
SET @participants_table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'certificate_participants'
);

SET @sql := IF(
    @participants_table_exists = 0,
    'CREATE TABLE certificate_participants (
        id BIGINT NOT NULL AUTO_INCREMENT,
        training_context_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL COMMENT ''users.id — salutation derived from users.salutation_id'',
        qualifies_for_cpd_override TINYINT(1) NULL,
        confirmation_status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
        certificate_id BIGINT NULL,
        created_by BIGINT NOT NULL,
        updated_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL,
        PRIMARY KEY (id),
        INDEX idx_certificate_participants_context (training_context_id),
        INDEX idx_certificate_participants_user (user_id),
        INDEX idx_certificate_participants_status (confirmation_status),
        INDEX idx_certificate_participants_deleted (deleted_at),
        CONSTRAINT fk_certificate_participants_context
            FOREIGN KEY (training_context_id) REFERENCES certificate_training_contexts (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''certificate_participants already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- 3. Seed default salutations (skip if label already present)
-- ---------------------------------------------------------------------------
INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'CPA', 'cpa', 1, 1, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'cpa');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'CPA. Dr.', 'cpa_dr', 1, 2, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'cpa_dr');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Dr.', 'dr', 0, 3, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'dr');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Mr.', 'mr', 0, 4, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'mr');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Ms.', 'ms', 0, 5, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'ms');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Mrs.', 'mrs', 0, 6, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'mrs');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'None', 'none', 0, 99, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'none');

SELECT 'Certificate participant tables migration complete' AS message;
