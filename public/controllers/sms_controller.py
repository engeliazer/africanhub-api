from flask import Blueprint, request, jsonify
import requests
import base64
import os
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

sms_bp = Blueprint('sms', __name__)

class SMSService:
    @staticmethod
    def send_message(phone: str, message: str, sender: str = "DCRC"):
        """
        Send SMS using Beem Africa API
        """
        # Log input parameters
        print(f"SMS Service - Input parameters:")
        print(f"  Phone: {phone}")
        print(f"  Message: {message}")
        print(f"  Sender: {sender}")
        
        # Format phone number (remove any spaces or special characters)
        phone = ''.join(filter(str.isdigit, phone))
        print(f"SMS Service - Formatted phone: {phone}")
        
        # API credentials
        api_key = os.getenv('BEEM_API_KEY', 'd23fa63bf5686ee1')
        secret_key = os.getenv('BEEM_SECRET_KEY', 'M2JhYjFkN2ZhZDFiMjZmYzczMjkwMzMzMTIwZjFkMjcxMzlhZWRhYTYxY2MwYmU4M2ExN2RkNGM5ZTFkYzQ3Nw==')
        
        # API endpoint
        url = 'https://apisms.beem.africa/v1/send'
        
        # Prepare request data
        post_data = {
            'source_addr': sender,
            'encoding': 0,
            'schedule_time': '',
            'message': message,
            'recipients': [
                {
                    'recipient_id': '1',
                    'dest_addr': phone
                }
            ]
        }
        
        # Log request data
        print(f"SMS Service - Request data: {post_data}")
        
        # Prepare headers
        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{api_key}:{secret_key}".encode()).decode()}',
            'Content-Type': 'application/json'
        }
        
        try:
            # Log the message before sending
            print(f"SMS Service - Sending request to Beem Africa API")
            
            response = requests.post(url, json=post_data, headers=headers)
            
            # Log response
            print(f"SMS Service - Response status code: {response.status_code}")
            print(f"SMS Service - Response text: {response.text}")
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'SMS sending failed: {response.text}'
                }
            
            result = response.json()
            return {
                'success': True,
                'data': result
            }
            
        except Exception as e:
            print(f"SMS Service - Error: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending SMS: {str(e)}'
            }

@sms_bp.route('/api/sms/send', methods=['POST'])
def send_sms():
    """
    Send an SMS message
    """
    data = request.get_json()
    phone = data.get('phone')
    message = data.get('message')
    sender = data.get('sender', 'DCRC')
    
    if not phone or not message:
        return jsonify({
            'success': False,
            'message': 'Phone and message are required'
        }), 400
    
    result = SMSService.send_message(phone, message, sender)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result) 