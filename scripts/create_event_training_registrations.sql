-- Manual alternative to Alembic revision gd4e5f6a7b8c.
CREATE TABLE event_training_registrations (
    id BIGINT NOT NULL AUTO_INCREMENT,
    event_id BIGINT NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    email VARCHAR(255) NOT NULL,
    organization VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_event_training_registrations_id (id),
    INDEX ix_event_training_registrations_event_id (event_id),
    CONSTRAINT uq_event_training_registration_email UNIQUE (event_id, email),
    FOREIGN KEY (event_id) REFERENCES events (id)
);
