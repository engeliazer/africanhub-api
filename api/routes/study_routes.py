from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
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
        categories = db.query(StudyMaterialCategory).all()
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