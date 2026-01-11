from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import Session
from typing import List
from functools import wraps
import jwt
from flask import current_app
from datetime import datetime

from database.db_connector import db_session
from chat.models.models import Chat, ChatMessage, ChatRating
from chat.models.schemas import ChatInDB, ChatMessageCreate, ChatMessageInDB, ChatRatingCreate, ChatRatingInDB
from auth.models.models import User, UserRole, Role

chat_bp = Blueprint('chat', __name__)

def admin_required():
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            current_user_id = get_jwt_identity()
            user = db_session.query(User).get(current_user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 401
            
            # Check if user has any admin role
            user_roles = db_session.query(UserRole).filter(
                UserRole.user_id == current_user_id,
                UserRole.is_active == True,
                UserRole.deleted_at.is_(None)
            ).all()
            
            has_admin_role = False
            for user_role in user_roles:
                role = db_session.query(Role).get(user_role.role_id)
                if role and role.code in ['ADMIN', 'SYSADMIN']:
                    has_admin_role = True
                    break
            
            if not has_admin_role:
                return jsonify({'error': 'Admin privileges required'}), 403
            
            return fn(*args, **kwargs)
        return decorator
    return wrapper

@chat_bp.route('/chat', methods=['GET'])
@jwt_required()
def get_chat_history():
    current_user_id = get_jwt_identity()
    user = db_session.query(User).get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    chat = db_session.query(Chat).filter_by(user_id=current_user_id, is_active=True).first()
    if not chat:
        chat = Chat(user_id=current_user_id, is_active=True)
        db_session.add(chat)
        db_session.commit()
    
    messages = db_session.query(ChatMessage).filter_by(chat_id=chat.id).order_by(ChatMessage.created_at).all()
    
    response = {
        'chat_id': chat.id,
        'messages': [ChatMessageInDB.from_orm(msg).dict() for msg in messages]
    }
    
    # Get the latest rating (if any)
    rating = db_session.query(ChatRating).filter_by(
        chat_id=chat.id,
        is_request=False,
        status='rated',
        deleted_at=None
    ).order_by(ChatRating.created_at.desc()).first()
    
    if rating:
        response['rating'] = ChatRatingInDB.from_orm(rating).dict()
    else:
        response['rating'] = {}
    
    # Get the latest pending rating request (if any)
    pending_request = db_session.query(ChatRating).filter_by(
        chat_id=chat.id,
        is_request=True,
        status='pending',
        deleted_at=None
    ).order_by(ChatRating.created_at.desc()).first()
    
    if pending_request:
        response['rating_request'] = {
            'requested_at': pending_request.created_at.isoformat(),
            'requested_by': pending_request.requested_by,
            'requester': {
                'id': pending_request.requester.id,
                'first_name': pending_request.requester.first_name,
                'last_name': pending_request.requester.last_name,
                'email': pending_request.requester.email
            } if pending_request.requester else {}
        }
    else:
        response['rating_request'] = {}
    
    return jsonify(response)

@chat_bp.route('/chat/message', methods=['POST'])
@jwt_required()
def send_message():
    current_user_id = get_jwt_identity()
    user = db_session.query(User).get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get the last active chat
    last_chat = db_session.query(Chat).filter_by(user_id=current_user_id, is_active=True).first()
    
    # If there's no active chat, create a new one
    if not last_chat:
        chat = Chat(user_id=current_user_id, is_active=True)
        db_session.add(chat)
        db_session.commit()
    else:
        chat = last_chat
    
    message = ChatMessage(
        chat_id=chat.id,
        sender_id=current_user_id,
        message=data['message'],
        is_from_user=True,
        is_read=False
    )
    db_session.add(message)
    db_session.commit()
    
    return jsonify(ChatMessageInDB.from_orm(message).dict())

@chat_bp.route('/chat/<int:chat_id>/reply', methods=['POST'])
@admin_required()
def reply_to_chat(chat_id):
    current_user_id = get_jwt_identity()
    admin = db_session.query(User).get(current_user_id)
    
    if not admin:
        return jsonify({'error': 'Admin not found'}), 401
    
    chat = db_session.query(Chat).get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
    
    message = ChatMessage(
        chat_id=chat_id,
        sender_id=current_user_id,
        message=data['message'],
        is_from_user=False,
        is_read=True
    )
    db_session.add(message)
    db_session.commit()
    
    return jsonify(ChatMessageInDB.from_orm(message).dict())

@chat_bp.route('/chat/all', methods=['GET'])
@jwt_required()
def get_all_chats():
    chats = db_session.query(Chat).filter_by(is_active=True).all()
    return jsonify({
        'chats': [{
            'id': chat.id,
            'user_id': chat.user_id,
            'user': {
                'id': chat.user.id,
                'email': chat.user.email,
                'first_name': chat.user.first_name,
                'last_name': chat.user.last_name
            },
            'created_at': chat.created_at.isoformat(),
            'messages': [ChatMessageInDB.from_orm(msg).dict() for msg in chat.messages]
        } for chat in chats]
    })

@chat_bp.route('/chat/<int:chat_id>/rate', methods=['POST'])
@jwt_required()
def rate_chat(chat_id):
    current_user_id = int(get_jwt_identity())
    user = db_session.query(User).get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    chat = db_session.query(Chat).get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    # Check if user owns the chat
    if chat.user_id != current_user_id:
        return jsonify({'error': 'Not authorized to rate this chat'}), 403
    
    # Check if there's a pending rating request
    pending_request = db_session.query(ChatRating).filter_by(
        chat_id=chat_id,
        is_request=True,
        status='pending',
        deleted_at=None
    ).first()
    
    if not pending_request:
        return jsonify({'error': 'No pending rating request found for this chat'}), 400
    
    data = request.get_json()
    if not data or 'rating' not in data:
        return jsonify({'error': 'Rating is required'}), 400
    
    # Validate rating is between 1 and 5
    rating_value = float(data['rating'])
    if rating_value < 1 or rating_value > 5:
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400
    
    # Update the rating request with the actual rating
    pending_request.rating = rating_value
    pending_request.comment = data.get('comment')
    pending_request.is_request = False
    pending_request.status = 'rated'
    
    db_session.commit()
    
    return jsonify(ChatRatingInDB.from_orm(pending_request).dict())

@chat_bp.route('/chat/<int:chat_id>/rating', methods=['GET'])
@jwt_required()
def get_chat_rating(chat_id):
    current_user_id = get_jwt_identity()
    user = db_session.query(User).get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    chat = db_session.query(Chat).get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    # Check if user owns the chat or is admin/support
    if chat.user_id != current_user_id:
        user_roles = db_session.query(UserRole).filter(
            UserRole.user_id == current_user_id,
            UserRole.is_active == True,
            UserRole.deleted_at.is_(None)
        ).all()
        
        has_admin_role = False
        for user_role in user_roles:
            role = db_session.query(Role).get(user_role.role_id)
            if role and role.code in ['ADMIN', 'SYSADMIN', 'SUPPORT']:
                has_admin_role = True
                break
        
        if not has_admin_role:
            return jsonify({'error': 'Not authorized to view this rating'}), 403
    
    # Get the latest rating (if any)
    rating = db_session.query(ChatRating).filter_by(
        chat_id=chat_id,
        is_request=False,
        status='rated',
        deleted_at=None
    ).order_by(ChatRating.created_at.desc()).first()
    
    if not rating:
        return jsonify({'error': 'No rating found for this chat'}), 404
    
    return jsonify(ChatRatingInDB.from_orm(rating).dict())

@chat_bp.route('/chat/<int:chat_id>/request-rating', methods=['POST'])
@admin_required()
def request_chat_rating(chat_id):
    current_user_id = get_jwt_identity()
    admin = db_session.query(User).get(current_user_id)
    
    if not admin:
        return jsonify({'error': 'Admin not found'}), 401
    
    chat = db_session.query(Chat).get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    # Check if there's already a pending rating request
    pending_request = db_session.query(ChatRating).filter_by(
        chat_id=chat_id,
        is_request=True,
        status='pending',
        deleted_at=None
    ).first()
    
    if pending_request:
        return jsonify({'error': 'A rating request is already pending for this chat'}), 400
    
    # Create new rating request
    rating_request = ChatRating(
        chat_id=chat_id,
        is_request=True,
        requested_by=current_user_id,
        status='pending'
    )
    db_session.add(rating_request)
    db_session.commit()
    
    return jsonify({
        'message': 'Rating request sent successfully',
        'chat_id': chat.id,
        'request_id': rating_request.id,
        'requested_at': rating_request.created_at.isoformat(),
        'requested_by': current_user_id
    })

@chat_bp.route('/chat/<int:chat_id>/decline-rating', methods=['POST'])
@jwt_required()
def decline_chat_rating(chat_id):
    current_user_id = get_jwt_identity()
    user = db_session.query(User).get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    chat = db_session.query(Chat).get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    # Check if user owns the chat or is admin/support
    if chat.user_id != current_user_id:
        user_roles = db_session.query(UserRole).filter(
            UserRole.user_id == current_user_id,
            UserRole.is_active == True,
            UserRole.deleted_at.is_(None)
        ).all()
        
        has_admin_role = False
        for user_role in user_roles:
            role = db_session.query(Role).get(user_role.role_id)
            if role and role.code in ['ADMIN', 'SYSADMIN', 'SUPPORT']:
                has_admin_role = True
                break
        
        if not has_admin_role:
            return jsonify({'error': 'Not authorized to decline rating for this chat'}), 403
    
    # Check if there's a pending rating request
    pending_request = db_session.query(ChatRating).filter_by(
        chat_id=chat_id,
        is_request=True,
        status='pending',
        deleted_at=None
    ).first()
    
    if not pending_request:
        return jsonify({'error': 'No pending rating request found for this chat'}), 400
    
    # Update the rating request status to declined
    pending_request.status = 'declined'
    db_session.commit()
    
    return jsonify({
        'message': 'Rating request declined successfully',
        'chat_id': chat.id,
        'request_id': pending_request.id
    })

@chat_bp.route('/chat/<int:chat_id>', methods=['GET'])
@jwt_required()
def get_chat_by_id(chat_id):
    current_user_id = get_jwt_identity()
    user = db_session.query(User).get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    chat = db_session.query(Chat).get(chat_id)
    if not chat:
        return jsonify({'message': 'Resource not found', 'status': 'error'}), 404
    
    # Check if user owns the chat or is admin/support
    if chat.user_id != current_user_id:
        user_roles = db_session.query(UserRole).filter(
            UserRole.user_id == current_user_id,
            UserRole.is_active == True,
            UserRole.deleted_at.is_(None)
        ).all()
        
        has_admin_role = False
        for user_role in user_roles:
            role = db_session.query(Role).get(user_role.role_id)
            if role and role.code in ['ADMIN', 'SYSADMIN', 'SUPPORT']:
                has_admin_role = True
                break
        
        if not has_admin_role:
            return jsonify({'error': 'Not authorized to view this chat'}), 403
    
    messages = db_session.query(ChatMessage).filter_by(chat_id=chat.id).order_by(ChatMessage.created_at).all()
    
    response = {
        'chat_id': chat.id,
        'user_id': chat.user_id,
        'user': {
            'id': chat.user.id,
            'email': chat.user.email,
            'first_name': chat.user.first_name,
            'last_name': chat.user.last_name
        },
        'messages': [ChatMessageInDB.from_orm(msg).dict() for msg in messages]
    }
    
    # Get the latest rating (if any)
    rating = db_session.query(ChatRating).filter_by(
        chat_id=chat.id,
        is_request=False,
        status='rated',
        deleted_at=None
    ).order_by(ChatRating.created_at.desc()).first()
    
    if rating:
        response['rating'] = ChatRatingInDB.from_orm(rating).dict()
    else:
        response['rating'] = {}
    
    # Get the latest pending rating request (if any)
    pending_request = db_session.query(ChatRating).filter_by(
        chat_id=chat.id,
        is_request=True,
        status='pending',
        deleted_at=None
    ).order_by(ChatRating.created_at.desc()).first()
    
    if pending_request:
        response['rating_request'] = {
            'id': pending_request.id,
            'requested_at': pending_request.created_at.isoformat(),
            'requested_by': pending_request.requested_by,
            'status': pending_request.status,
            'requester': {
                'id': pending_request.requester.id,
                'first_name': pending_request.requester.first_name,
                'last_name': pending_request.requester.last_name,
                'email': pending_request.requester.email
            } if pending_request.requester else {}
        }
    else:
        response['rating_request'] = {}
    
    # Get all ratings and rating requests
    all_ratings = db_session.query(ChatRating).filter(
        ChatRating.chat_id == chat.id,
        ChatRating.deleted_at.is_(None)
    ).order_by(ChatRating.created_at.desc()).all()
    
    # Group ratings and requests together
    rating_history = []
    request_id_to_rating = {}
    
    # First, identify all rating requests and create a mapping
    for entry in all_ratings:
        if entry.is_request and entry.status == 'pending':
            # Add entry for the pending request
            request_entry = ChatRatingInDB.from_orm(entry).dict()
            request_entry['type'] = 'request'
            request_entry['requester'] = {
                'id': entry.requester.id,
                'first_name': entry.requester.first_name,
                'last_name': entry.requester.last_name,
                'email': entry.requester.email
            } if entry.requester else {}
            rating_history.append(request_entry)
        elif not entry.is_request and entry.status == 'rated':
            # This is a completed rating
            rating_entry = ChatRatingInDB.from_orm(entry).dict()
            rating_entry['type'] = 'rating'
            rating_entry['requester'] = {
                'id': entry.requester.id,
                'first_name': entry.requester.first_name,
                'last_name': entry.requester.last_name,
                'email': entry.requester.email
            } if entry.requester else {}
            rating_history.append(rating_entry)
        elif entry.is_request and entry.status == 'declined':
            # This is a declined request
            declined_entry = ChatRatingInDB.from_orm(entry).dict()
            declined_entry['type'] = 'declined'
            declined_entry['requester'] = {
                'id': entry.requester.id,
                'first_name': entry.requester.first_name,
                'last_name': entry.requester.last_name,
                'email': entry.requester.email
            } if entry.requester else {}
            rating_history.append(declined_entry)
    
    response['rating_history'] = rating_history
    
    return jsonify(response) 