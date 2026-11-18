from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from database.db_connector import get_db
from studies.models.models import StudyMaterialCategory, SubtopicMaterial
from studies.models.schemas import (
    StudyMaterialCategoryCreate, StudyMaterialCategoryUpdate, StudyMaterialCategoryInDB,
    SubtopicMaterialCreate, SubtopicMaterialUpdate, SubtopicMaterialInDB
)

# Create blueprints for study-related entities
material_categories_bp = Blueprint('material_categories', __name__)

# Study Material Category routes
@material_categories_bp.route('/study-materials/categories', methods=['GET'])
@jwt_required()
def get_material_categories():
    try:
        db = get_db()
        categories = db.query(StudyMaterialCategory).order_by(StudyMaterialCategory.code.asc()).all()
        return jsonify({
            "status": "success",
            "data": [StudyMaterialCategoryInDB.from_orm(category).dict() for category in categories]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@material_categories_bp.route('/study-materials/categories/<int:category_id>', methods=['GET'])
@jwt_required()
def get_material_category(category_id):
    try:
        db = get_db()
        category = db.query(StudyMaterialCategory).filter(StudyMaterialCategory.id == category_id).first()
        if not category:
            return jsonify({
                "status": "error",
                "message": "Material category not found"
            }), 404
        return jsonify({
            "status": "success",
            "data": StudyMaterialCategoryInDB.from_orm(category).dict()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@material_categories_bp.route('/study-materials/categories', methods=['POST'])
@jwt_required()
def create_material_category():
    try:
        db = get_db()
        data = request.get_json()
        category_data = StudyMaterialCategoryCreate(**data)
        category = StudyMaterialCategory(**category_data.dict())
        db.add(category)
        db.commit()
        db.refresh(category)
        return jsonify({
            "status": "success",
            "data": StudyMaterialCategoryInDB.from_orm(category).dict()
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        db.close()

@material_categories_bp.route('/study-materials/categories/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_material_category(category_id):
    try:
        db = get_db()
        category = db.query(StudyMaterialCategory).filter(
            StudyMaterialCategory.id == category_id,
            StudyMaterialCategory.deleted_at.is_(None)
        ).first()
        if not category:
            return jsonify({
                "status": "error",
                "message": "Material category not found"
            }), 404

        data = request.get_json(silent=True) or {}
        data['updated_by'] = int(get_jwt_identity())
        category_data = StudyMaterialCategoryUpdate(**data)

        for field, value in category_data.dict(exclude_unset=True).items():
            setattr(category, field, value)

        db.commit()
        db.refresh(category)
        return jsonify({
            "status": "success",
            "data": StudyMaterialCategoryInDB.from_orm(category).dict()
        })
    except IntegrityError:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": "Category code already exists"
        }), 400
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()

@material_categories_bp.route('/study-materials/categories/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_material_category(category_id):
    try:
        db = get_db()
        category = db.query(StudyMaterialCategory).filter(
            StudyMaterialCategory.id == category_id,
            StudyMaterialCategory.deleted_at.is_(None)
        ).first()
        if not category:
            return jsonify({
                "status": "error",
                "message": "Material category not found"
            }), 404

        category.deleted_at = datetime.utcnow()
        category.updated_by = int(get_jwt_identity())
        db.commit()
        return jsonify({
            "status": "success",
            "message": "Category deleted successfully"
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    finally:
        db.close()