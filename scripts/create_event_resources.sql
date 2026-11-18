-- Manual alternative to Alembic revision ge5f6a7b8c9d.
CREATE TABLE IF NOT EXISTS event_resources (
    id BIGINT NOT NULL AUTO_INCREMENT,
    event_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    file_path VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255) NULL,
    extension_type VARCHAR(20) NOT NULL DEFAULT 'zip',
    file_size BIGINT NULL,
    created_by BIGINT NOT NULL,
    updated_by BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    INDEX ix_event_resources_id (id),
    INDEX ix_event_resources_event_id (event_id),
    CONSTRAINT fk_event_resources_event_id
        FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
);
