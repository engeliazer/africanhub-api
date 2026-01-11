#!/usr/bin/env python3
"""
Migration script to create testimonials table
Run this script to add the testimonials table to your database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_connector import db_session
from sqlalchemy import text

def create_testimonials_table():
    """Create the testimonials table"""
    try:
        # Create testimonials table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS testimonials (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            role VARCHAR(255),
            text TEXT NOT NULL,
            photo VARCHAR(500),
            rating INT NOT NULL DEFAULT 5,
            is_approved BOOLEAN NOT NULL DEFAULT FALSE,
            reviewed_by BIGINT NULL,
            reviewed_at DATETIME NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by BIGINT NOT NULL,
            updated_by BIGINT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            deleted_at DATETIME NULL,
            INDEX idx_testimonials_user (user_id),
            INDEX idx_testimonials_approved (is_approved),
            INDEX idx_testimonials_active (is_active),
            INDEX idx_testimonials_deleted (deleted_at),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        db_session.execute(text(create_table_sql))
        db_session.commit()
        print("✅ Testimonials table created successfully!")
        
        # Insert sample data (assuming users with IDs 1 and 2 exist)
        sample_testimonials = [
            {
                'user_id': 1,  # Assuming user ID 1 exists
                'role': 'CPA Graduate, 2024',
                'text': 'DCRC provided me with the best CPA review experience. The instructors are knowledgeable, the materials are comprehensive, and the support is exceptional. I passed all my exams on the first attempt!',
                'photo': 'https://api.ocpac.dcrc.ac.tz/storage/testimonials/james-mwenda.jpg',
                'rating': 5,
                'is_approved': True,  # Pre-approved for demo
                'reviewed_by': 1,
                'reviewed_at': '2024-01-15 10:00:00',
                'created_by': 1,
                'updated_by': 1
            },
            {
                'user_id': 2,  # Assuming user ID 2 exists
                'role': 'CPA Graduate, 2023',
                'text': 'The structured approach to teaching and the practical examples made complex topics easy to understand. I highly recommend DCRC to anyone serious about becoming a CPA.',
                'photo': 'https://api.ocpac.dcrc.ac.tz/storage/testimonials/amina-hassan.jpg',
                'rating': 5,
                'is_approved': True,  # Pre-approved for demo
                'reviewed_by': 1,
                'reviewed_at': '2024-01-15 10:00:00',
                'created_by': 1,
                'updated_by': 1
            }
        ]
        
        for testimonial in sample_testimonials:
            insert_sql = """
            INSERT INTO testimonials (user_id, role, text, photo, rating, is_approved, reviewed_by, reviewed_at, is_active, created_by, updated_by)
            VALUES (:user_id, :role, :text, :photo, :rating, :is_approved, :reviewed_by, :reviewed_at, :is_active, :created_by, :updated_by)
            """
            db_session.execute(text(insert_sql), testimonial)
        
        db_session.commit()
        print("✅ Sample testimonial data inserted successfully!")
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ Error creating testimonials table: {str(e)}")
        return False
    finally:
        db_session.close()
    
    return True

if __name__ == "__main__":
    print("🚀 Creating testimonials table...")
    success = create_testimonials_table()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
        sys.exit(1)
