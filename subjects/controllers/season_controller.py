from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound, BadRequest
from typing import List, Optional
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import and_, not_

from subjects.models.models import Season, SeasonSubject
from subjects.models.schemas import SeasonCreate, SeasonUpdate, SeasonInDB
from applications.models.models import ApplicationDetail, Application, ApplicationStatus
from database.db_connector import db_session

season_bp = Blueprint('season', __name__)

class SeasonsController:
    def __init__(self, db: Session):
        self.db = db

    def create_season(self, season: SeasonCreate) -> SeasonInDB:
        """Create a new season"""
        try:
            db_season = Season(
                name=season.name,
                code=season.code,
                description=season.description,
                is_active=season.is_active,
                created_by=season.created_by,
                updated_by=season.updated_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(db_season)
            self.db.commit()
            self.db.refresh(db_season)
            return SeasonInDB.from_orm(db_season)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Season code already exists")

    def get_season(self, season_id: int) -> Optional[SeasonInDB]:
        """Get a season by ID"""
        season = self.db.query(Season).filter(
            Season.id == season_id,
            Season.deleted_at.is_(None)
        ).first()
        if not season:
            raise NotFound("Season not found")
        return SeasonInDB.from_orm(season)

    def get_seasons(self, skip: int = 0, limit: int = 100) -> List[SeasonInDB]:
        """Get all seasons with pagination"""
        seasons = self.db.query(Season).filter(
            Season.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()
        return [SeasonInDB.from_orm(season) for season in seasons]

    def update_season(self, season_id: int, season_update: SeasonUpdate) -> SeasonInDB:
        """Update a season"""
        db_season = self.db.query(Season).filter(
            Season.id == season_id,
            Season.deleted_at.is_(None)
        ).first()
        if not db_season:
            raise NotFound("Season not found")

        update_data = season_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_season, field, value)

        db_season.updated_at = datetime.utcnow()

        try:
            self.db.commit()
            self.db.refresh(db_season)
            return SeasonInDB.from_orm(db_season)
        except IntegrityError:
            self.db.rollback()
            raise BadRequest("Season code already exists")

    def delete_season(self, season_id: int) -> bool:
        """Soft delete a season"""
        db_season = self.db.query(Season).filter(
            Season.id == season_id,
            Season.deleted_at.is_(None)
        ).first()
        if not db_season:
            raise NotFound("Season not found")

        db_season.deleted_at = datetime.utcnow()
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise BadRequest("Could not delete season")

    def get_available_seasons(self, user_id: int) -> List[SeasonInDB]:
        """Get all seasons that have subjects the user hasn't applied for"""
        # Get all seasons that are active and have subjects
        seasons_with_subjects = self.db.query(Season).join(
            SeasonSubject
        ).filter(
            and_(
                Season.is_active == True,
                SeasonSubject.is_active == True,
                Season.deleted_at.is_(None)
            )
        ).distinct().all()

        # Get all seasons the user has already applied for (excluding withdrawn applications)
        applied_seasons = self.db.query(ApplicationDetail.season_id)\
            .join(Application, ApplicationDetail.application_id == Application.id)\
            .filter(
                and_(
                    Application.user_id == user_id,
                    Application.is_active == True,
                    ApplicationDetail.is_active == True,
                    ApplicationDetail.deleted_at.is_(None),
                    Application.status != ApplicationStatus.withdrawn.value  # Exclude withdrawn applications
                )
            ).distinct().all()
        applied_season_ids = [season[0] for season in applied_seasons]

        # Filter out seasons the user has already applied for
        available_seasons = [
            season for season in seasons_with_subjects 
            if season.id not in applied_season_ids
        ]

        return [SeasonInDB.from_orm(season) for season in available_seasons]

# API Routes
@season_bp.route('/api/seasons', methods=['POST'])
@jwt_required()
def create_season():
    """Create a new season"""
    try:
        data = request.get_json()
        season_data = SeasonCreate(**data)
        controller = SeasonsController(db_session)
        season = controller.create_season(season_data)
        return jsonify({
            "status": "success",
            "message": "Season created successfully",
            "data": season.dict()
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@season_bp.route('/api/seasons', methods=['GET'])
@jwt_required()
def get_seasons():
    """Get all seasons"""
    try:
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        controller = SeasonsController(db_session)
        seasons = controller.get_seasons(skip, limit)
        return jsonify({
            "status": "success",
            "message": "Seasons retrieved successfully",
            "data": {
                "seasons": [season.dict() for season in seasons]
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@season_bp.route('/api/seasons/<int:season_id>', methods=['GET'])
@jwt_required()
def get_season(season_id):
    """Get a specific season"""
    try:
        controller = SeasonsController(db_session)
        season = controller.get_season(season_id)
        return jsonify({
            "status": "success",
            "message": "Season retrieved successfully",
            "data": season.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404

@season_bp.route('/api/seasons/<int:season_id>', methods=['PUT'])
@jwt_required()
def update_season(season_id):
    """Update a season"""
    try:
        data = request.get_json()
        season_data = SeasonUpdate(**data)
        controller = SeasonsController(db_session)
        season = controller.update_season(season_id, season_data)
        return jsonify({
            "status": "success",
            "message": "Season updated successfully",
            "data": season.dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@season_bp.route('/api/seasons/<int:season_id>', methods=['DELETE'])
@jwt_required()
def delete_season(season_id):
    """Delete a season"""
    try:
        controller = SeasonsController(db_session)
        success = controller.delete_season(season_id)
        return jsonify({
            "status": "success",
            "message": "Season deleted successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404

@season_bp.route('/api/seasons/available-seasons', methods=['GET'])
@jwt_required()
def get_available_seasons():
    """Get all seasons that have subjects the user hasn't applied for"""
    try:
        # Get current user ID from JWT token
        current_user_id = get_jwt_identity()
        
        controller = SeasonsController(db_session)
        seasons = controller.get_available_seasons(current_user_id)
        
        return jsonify({
            "status": "success",
            "data": [season.dict() for season in seasons]
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db_session.remove() 