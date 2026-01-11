from datetime import datetime
from sqlalchemy.orm import Session
from auth.models.models import Role

def seed_roles(session: Session):
    """Seed default roles into the database."""
    default_roles = [
        {
            "name": "Super Admin",
            "code": "SUPADM",
            "description": "Super administrator with complete system access",
            "is_active": True,
            "created_by": 1,
            "updated_by": 1
        },
        {
            "name": "System Admin",
            "code": "SYSADMIN",
            "description": "System administrator with administrative access",
            "is_active": True,
            "created_by": 1,
            "updated_by": 1
        },
        {
            "name": "Facilitator",
            "code": "FACILITATOR",
            "description": "Facilitator role for managing courses and students",
            "is_active": True,
            "created_by": 1,
            "updated_by": 1
        },
        {
            "name": "Student",
            "code": "STUDENT",
            "description": "Regular student role",
            "is_active": True,
            "created_by": 1,
            "updated_by": 1
        }
    ]

    for role_data in default_roles:
        # Check if role already exists
        existing_role = session.query(Role).filter_by(code=role_data["code"]).first()
        if not existing_role:
            # Create new role
            role = Role(
                name=role_data["name"],
                code=role_data["code"],
                description=role_data["description"],
                is_active=role_data["is_active"],
                created_by=role_data["created_by"],
                updated_by=role_data["updated_by"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(role)
    
    try:
        session.commit()
        print("Default roles seeded successfully")
    except Exception as e:
        session.rollback()
        print(f"Error seeding roles: {str(e)}")
        raise

def run_seeders(session: Session):
    """Run all database seeders."""
    print("Starting database seeding...")
    seed_roles(session)
    print("Database seeding completed") 