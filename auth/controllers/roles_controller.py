from sqlalchemy.orm import Session
from typing import List
from auth.models.models import Role
from auth.models.schemas import RoleInDB, RoleCreate
from datetime import datetime

class RolesController:
    @staticmethod
    def get_roles(db: Session) -> List[RoleInDB]:
        roles = db.query(Role).filter(Role.deleted_at.is_(None)).all()
        return [RoleInDB.from_orm(role) for role in roles]

    @staticmethod
    def get_role(db: Session, role_id: int) -> RoleInDB:
        role = db.query(Role).filter(Role.id == role_id, Role.deleted_at.is_(None)).first()
        if role is None:
            return None
        return RoleInDB.from_orm(role)
        
    @staticmethod
    def create_role(db: Session, role_data: RoleCreate) -> RoleInDB:
        """Create a new role"""
        db_role = Role(
            name=role_data.name,
            code=role_data.code,
            description=role_data.description,
            is_active=role_data.is_active,
            created_by=role_data.created_by,
            updated_by=role_data.updated_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return RoleInDB.from_orm(db_role) 