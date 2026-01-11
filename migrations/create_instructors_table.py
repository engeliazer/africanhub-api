#!/usr/bin/env python3
"""
Migration script to create instructors table
Run this script to add the instructors table to your database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_connector import db_session
from sqlalchemy import text

def create_instructors_table():
    """Create the instructors table"""
    try:
        # Create instructors table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS instructors (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            title VARCHAR(255),
            bio TEXT,
            photo VARCHAR(500),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by BIGINT NOT NULL,
            updated_by BIGINT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            deleted_at DATETIME NULL,
            INDEX idx_instructors_active (is_active),
            INDEX idx_instructors_deleted (deleted_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        db_session.execute(text(create_table_sql))
        db_session.commit()
        print("✅ Instructors table created successfully!")
        
        # Insert sample data
        sample_instructors = [
            {
                'name': 'Dr. John Mwangi',
                'title': 'CPA, PhD in Accounting',
                'bio': 'Dr. Mwangi is a seasoned accounting professional with extensive experience in financial reporting and auditing.',
                'photo': 'https://api.ocpac.dcrc.ac.tz/storage/instructors/dr-john-mwangi.jpg',
                'created_by': 1,
                'updated_by': 1
            },
            {
                'name': 'Ms. Sarah Kimani',
                'title': 'CPA, MSc Finance',
                'bio': 'Ms. Kimani specializes in management accounting and has helped hundreds of students excel in their exams.',
                'photo': 'https://api.ocpac.dcrc.ac.tz/storage/instructors/sarah-kimani.jpg',
                'created_by': 1,
                'updated_by': 1
            },
            {
                'name': 'Mr. David Omondi',
                'title': 'CPA, LLM Taxation',
                'bio': 'Mr. Omondi is a tax expert with a strong background in both taxation and business law.',
                'photo': 'https://api.ocpac.dcrc.ac.tz/storage/instructors/david-omondi.jpg',
                'created_by': 1,
                'updated_by': 1
            }
        ]
        
        for instructor in sample_instructors:
            insert_sql = """
            INSERT INTO instructors (name, title, bio, photo, is_active, created_by, updated_by)
            VALUES (:name, :title, :bio, :photo, :is_active, :created_by, :updated_by)
            """
            db_session.execute(text(insert_sql), instructor)
        
        db_session.commit()
        print("✅ Sample instructor data inserted successfully!")
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ Error creating instructors table: {str(e)}")
        return False
    finally:
        db_session.close()
    
    return True

if __name__ == "__main__":
    print("🚀 Creating instructors table...")
    success = create_instructors_table()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
        sys.exit(1)
