from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from studies.models.models import StudyMaterialCategory
from studies.models.schemas import StudyMaterialCategoryCreate, StudyMaterialCategoryUpdate, StudyMaterialCategoryInDB
from database.db_connector import db_session
from datetime import datetime

material_categories_bp = Blueprint('material_categories', __name__)

@material_categories_bp.route('/study-materials/categories', methods=['GET'])
@jwt_required()
def get_material_categories():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        skip = (page - 1) * per_page

        # Get total count
        total = db_session.query(StudyMaterialCategory).filter(StudyMaterialCategory.deleted_at.is_(None)).count()
        
        # Get paginated categories
        categories = db_session.query(StudyMaterialCategory).filter(
            StudyMaterialCategory.deleted_at.is_(None)
        ).offset(skip).limit(per_page).all()

        return jsonify({
            "items": [{
                "id": category.id,
                "name": category.name,
                "code": category.code,
                "description": category.description,
                "is_protected": category.is_protected,
                "created_at": category.created_at.isoformat() if category.created_at else None,
                "updated_at": category.updated_at.isoformat() if category.updated_at else None
            } for category in categories],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@material_categories_bp.route('/study-materials/categories', methods=['POST'])
@jwt_required()
def create_material_category():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Add the created_by and updated_by fields
        data['created_by'] = int(current_user_id)
        data['updated_by'] = int(current_user_id)
        
        category_data = StudyMaterialCategoryCreate(**data)
        db_category = StudyMaterialCategory(**category_data.dict())
        db_session.add(db_category)
        db_session.commit()
        db_session.refresh(db_category)
        
        return jsonify({
            "id": db_category.id,
            "name": db_category.name,
            "code": db_category.code,
            "description": db_category.description,
            "is_protected": db_category.is_protected,
            "created_at": db_category.created_at.isoformat() if db_category.created_at else None,
            "updated_at": db_category.updated_at.isoformat() if db_category.updated_at else None
        }), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@material_categories_bp.route('/study-materials/categories/<int:category_id>', methods=['GET'])
@jwt_required()
def get_material_category(category_id):
    try:
        category = db_session.query(StudyMaterialCategory).filter(
            StudyMaterialCategory.id == category_id,
            StudyMaterialCategory.deleted_at.is_(None)
        ).first()
        
        if not category:
            return jsonify({"error": "Category not found"}), 404
            
        return jsonify({
            "id": category.id,
            "name": category.name,
            "code": category.code,
            "description": category.description,
            "is_protected": category.is_protected,
            "created_at": category.created_at.isoformat() if category.created_at else None,
            "updated_at": category.updated_at.isoformat() if category.updated_at else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@material_categories_bp.route('/study-materials/categories/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_material_category(category_id):
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        data['updated_by'] = int(current_user_id)
        
        category_data = StudyMaterialCategoryUpdate(**data)
        category = db_session.query(StudyMaterialCategory).filter(
            StudyMaterialCategory.id == category_id,
            StudyMaterialCategory.deleted_at.is_(None)
        ).first()
        
        if not category:
            return jsonify({"error": "Category not found"}), 404
            
        for field, value in category_data.dict(exclude_unset=True).items():
            setattr(category, field, value)
            
        db_session.commit()
        db_session.refresh(category)
        
        return jsonify({
            "id": category.id,
            "name": category.name,
            "code": category.code,
            "description": category.description,
            "is_protected": category.is_protected,
            "created_at": category.created_at.isoformat() if category.created_at else None,
            "updated_at": category.updated_at.isoformat() if category.updated_at else None
        })
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@material_categories_bp.route('/study-materials/categories/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_material_category(category_id):
    try:
        current_user_id = get_jwt_identity()
        category = db_session.query(StudyMaterialCategory).filter(
            StudyMaterialCategory.id == category_id,
            StudyMaterialCategory.deleted_at.is_(None)
        ).first()
        
        if not category:
            return jsonify({"error": "Category not found"}), 404
            
        # Soft delete
        category.deleted_at = datetime.utcnow()
        category.updated_by = current_user_id
        db_session.commit()
        
        return jsonify({"message": "Category deleted successfully"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400 