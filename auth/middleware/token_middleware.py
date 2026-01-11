from flask import request, make_response, Response, g
from functools import wraps
from flask_jwt_extended import get_jwt, create_access_token, get_jwt_identity, verify_jwt_in_request
import time
from datetime import timedelta

def token_refresh_middleware():
    try:
        # Skip if no JWT is present
        if not request.headers.get('Authorization'):
            return None
            
        verify_jwt_in_request()
        current_token = get_jwt()
        current_time = time.time()
        
        # Check if token is close to expiration (5 minutes threshold)
        if current_token['exp'] - current_time < 300:
            # Check if within maximum session duration (24 hours)
            if current_time - current_token['iat'] < 86400:  # 24 hours in seconds
                # Generate new token
                new_token = create_access_token(
                    identity=get_jwt_identity(),
                    expires_delta=timedelta(minutes=30)  # New token valid for 30 minutes
                )
                
                # Store the new token in Flask's g object for response processing
                g.new_token = new_token
                
        return None
    except Exception:
        # If any error occurs during token refresh, continue without refreshing
        return None

def add_refreshed_token_to_response(response):
    """Add refreshed token to response headers if available"""
    if hasattr(g, 'new_token') and g.new_token:
        response.headers['X-New-Token'] = g.new_token
        response.headers['X-Token-Refreshed'] = 'true'
    return response 