from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask_jwt_extended import jwt_required, get_jwt_identity

from auth.models.models import User, UserRole, Role
from auth.models.schemas import UserCreate, UserUpdate, UserResponse, RoleInDB

class UsersController:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user: UserCreate) -> UserResponse:
        """Create a new user"""
        try:
            hashed_password = generate_password_hash(user.password)
            db_user = User(
                first_name=user.first_name,
                middle_name=user.middle_name,
                last_name=user.last_name,
                phone=user.phone,
                email=user.email,
                password=hashed_password,
                status=user.status,
                reset_password=False,
                registration_mode=user.registration_mode,
                created_by=get_jwt_identity().get('user_id'),
                updated_by=get_jwt_identity().get('user_id'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            
            # Create user roles
            for role_id in user.roles:
                user_role = UserRole(
                    user_id=db_user.id,
                    role_id=role_id,
                    created_by=get_jwt_identity().get('user_id'),
                    updated_by=get_jwt_identity().get('user_id'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.db.add(user_role)
            
            self.db.commit()
            
            # Convert to response model
            return self._to_response(db_user)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Email or phone already exists")

    def get_user(self, user_id: int) -> Optional[UserResponse]:
        """Get a user by ID"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFound("User not found")
        return self._to_response(user)

    def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Get a user by email"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise NotFound("User not found")
        return self._to_response(user)

    def get_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        """Get all users with pagination"""
        users = self.db.query(User).offset(skip).limit(limit).all()
        return [self._to_response(user) for user in users]

    def update_user(self, user_id: int, user_update: UserUpdate) -> UserResponse:
        """Update a user"""
        db_user = self.db.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise NotFound("User not found")

        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)

        db_user.updated_at = datetime.utcnow()

        try:
            self.db.commit()
            self.db.refresh(db_user)
            return self._to_response(db_user)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Email or phone already exists")

    def _to_response(self, user: User) -> UserResponse:
        """Convert User model to UserResponse schema"""
        # Get user roles with complete role information
        user_roles = self.db.query(UserRole).join(Role).filter(
            UserRole.user_id == user.id,
            Role.deleted_at.is_(None)
        ).all()

        # Convert roles to RoleInDB format and find default role
        roles = []
        default_role_name = None
        for ur in user_roles:
            role = ur.role  # Get the role from the relationship
            role_data = RoleInDB(
                id=role.id,
                name=role.name,
                code=role.code,
                description=role.description,
                is_active=role.is_active,
                created_by=role.created_by,
                updated_by=role.updated_by,
                created_at=role.created_at,
                updated_at=role.updated_at,
                deleted_at=role.deleted_at
            )
            roles.append(role_data)
            
            # If this is the default role, store its name
            if ur.is_default:
                default_role_name = role.name

        return UserResponse(
            id=user.id,
            first_name=user.first_name,
            middle_name=user.middle_name,
            last_name=user.last_name,
            phone=user.phone,
            email=user.email,
            status=user.status,
            registration_mode=user.registration_mode,
            reset_password=user.reset_password,
            created_by=user.created_by,
            updated_by=user.updated_by,
            email_verified_at=user.email_verified_at,
            remember_token=user.remember_token,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
            roles=roles,
            default_role=default_role_name
        ) 