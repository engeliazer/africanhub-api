from sqlalchemy import text

def upgrade(session):
    # Create sub_topics table if it doesn't exist
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS sub_topics (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            topic_id BIGINT NOT NULL,
            name VARCHAR(255) NOT NULL,
            code VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by BIGINT NOT NULL,
            updated_by BIGINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        )
    """))
    session.commit() 