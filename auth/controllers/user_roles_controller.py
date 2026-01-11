from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional
from datetime import datetime

from auth.models.models import UserRole, User, Role
from auth.models.schemas import UserRoleCreate, UserRoleResponse, UserRoleUpdate

class UserRolesController:
    def __init__(self, db: Session):
        self.db = db

    def create_user_role(self, user_role: UserRoleCreate) -> UserRoleResponse:
        """Create a new user role"""
        try:
            # Check if user exists
            user = self.db.query(User).filter(User.id == user_role.user_id).first()
            if not user:
                raise NotFound("User not found")

            # Check if role exists
            role = self.db.query(Role).filter(Role.id == user_role.role_id).first()
            if not role:
                raise NotFound("Role not found")

            # Check if user-role combination already exists
            existing = self.db.query(UserRole).filter(
                UserRole.user_id == user_role.user_id,
                UserRole.role_id == user_role.role_id
            ).first()
            if existing:
                raise BadRequest("User already has this role")

            db_user_role = UserRole(
                user_id=user_role.user_id,
                role_id=user_role.role_id,
                is_default=user_role.is_default,
                is_active=user_role.is_active,
                created_by=user_role.created_by,
                updated_by=user_role.updated_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(db_user_role)
            self.db.commit()
            self.db.refresh(db_user_role)
            return self._to_response(db_user_role)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Invalid user or role ID")

    def get_user_role(self, user_role_id: int) -> Optional[UserRoleResponse]:
        """Get a user role by ID"""
        user_role = self.db.query(UserRole).filter(UserRole.id == user_role_id).first()
        if not user_role:
            raise NotFound("User role not found")
        return self._to_response(user_role)

    def get_user_roles(self, skip: int = 0, limit: int = 100) -> List[UserRoleResponse]:
        """Get all user roles with pagination"""
        user_roles = self.db.query(UserRole).offset(skip).limit(limit).all()
        return [self._to_response(ur) for ur in user_roles]

    def get_roles_by_user(self, user_id: int) -> List[UserRoleResponse]:
        """Get all roles for a specific user"""
        user_roles = self.db.query(UserRole).join(Role).filter(
            UserRole.user_id == user_id,
            Role.deleted_at.is_(None)
        ).all()
        return [self._to_response(ur) for ur in user_roles]

    def get_users_by_role(self, role_id: int) -> List[UserRoleResponse]:
        """Get all users for a specific role"""
        user_roles = self.db.query(UserRole).filter(UserRole.role_id == role_id).all()
        return [self._to_response(ur) for ur in user_roles]

    def update_user_role(self, user_role_id: int, user_role_update: UserRoleUpdate) -> UserRoleResponse:
        """Update a user role"""
        db_user_role = self.db.query(UserRole).filter(UserRole.id == user_role_id).first()
        if not db_user_role:
            raise NotFound("User role not found")

        update_data = user_role_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user_role, field, value)

        db_user_role.updated_at = datetime.utcnow()

        try:
            self.db.commit()
            self.db.refresh(db_user_role)
            return self._to_response(db_user_role)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Invalid update data")

    def delete_user_role(self, user_role_id: int) -> bool:
        """Delete a user role"""
        db_user_role = self.db.query(UserRole).filter(UserRole.id == user_role_id).first()
        if not db_user_role:
            raise NotFound("User role not found")

        try:
            self.db.delete(db_user_role)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise BadRequest("Could not delete user role")

    def _to_response(self, user_role: UserRole) -> UserRoleResponse:
        """Convert UserRole model to UserRoleResponse schema"""
        return UserRoleResponse(
            id=user_role.id,
            user_id=user_role.user_id,
            role_id=user_role.role_id,
            is_default=user_role.is_default,
            name=user_role.role.name,
            code=user_role.role.code,
            created_at=user_role.created_at,
            updated_at=user_role.updated_at
        ) 