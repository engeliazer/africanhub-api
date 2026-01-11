"""
Contact Form Controller
Handles public contact form submissions and sends emails via SendGrid API or SMTP
"""

from flask import Blueprint, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import logging

# Try to import SendGrid (optional - falls back to SMTP if not available)
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
contact_bp = Blueprint('contact', __name__)


def validate_contact_data(data):
    """Validate contact form data"""
    required_fields = ['name', 'email', 'subject', 'message']
    
    for field in required_fields:
        if not data.get(field):
            return False, f"Missing required field: {field}"
    
    # Basic email validation
    email = data.get('email', '')
    if '@' not in email or '.' not in email:
        return False, "Invalid email address"
    
    return True, None


def send_contact_email_sendgrid_api(name, email, phone, subject, message):
    """
    Send contact form email via SendGrid API (HTTPS - works on DigitalOcean)
    
    Args:
        name: Sender's name
        email: Sender's email
        phone: Sender's phone (optional)
        subject: Email subject category
        message: Email message content
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        email_from = os.getenv('EMAIL_FROM')
        email_to = os.getenv('EMAIL_TO')
        email_cc = os.getenv('EMAIL_CC')  # Optional CC recipient
        
        if not all([sendgrid_api_key, email_from, email_to]):
            logger.error("Missing SendGrid configuration in environment variables")
            return False, "Email service not configured"
        
        # Create email content
        text_content = f"""New Contact Form Submission

Name: {name}
Email: {email}
Phone: {phone or 'Not provided'}
Subject: {subject}

Message:
{message}

---
This email was sent from the DCRC contact form at dcrc.ac.tz"""
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #285F68; margin-bottom: 20px;">New Contact Form Submission</h2>
        
        <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 10px 0;"><strong>Name:</strong> {name}</p>
            <p style="margin: 10px 0;"><strong>Email:</strong> <a href="mailto:{email}" style="color: #285F68;">{email}</a></p>
            <p style="margin: 10px 0;"><strong>Phone:</strong> {phone or 'Not provided'}</p>
            <p style="margin: 10px 0;"><strong>Subject:</strong> {subject}</p>
        </div>
        
        <div style="margin: 20px 0;">
            <h3 style="color: #285F68; margin-bottom: 10px;">Message:</h3>
            <div style="background: #ffffff; padding: 15px; border-left: 4px solid #285F68; line-height: 1.6; color: #333;">
                {message.replace(chr(10), '<br>')}
            </div>
        </div>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        
        <p style="color: #666; font-size: 12px; margin: 10px 0;">
            This email was sent from the DCRC contact form at <a href="https://dcrc.ac.tz" style="color: #285F68;">dcrc.ac.tz</a>
        </p>
        
        <p style="color: #666; font-size: 12px; margin: 10px 0;">
            You can reply directly to this email to respond to {name}.
        </p>
    </div>
</body>
</html>"""
        
        # Create SendGrid message
        # Use string format for emails (more reliable with SendGrid Python library)
        mail = Mail(
            from_email=(email_from, "DCRC Contact Form"),  # Tuple format: (email, name)
            to_emails=[email_to],  # List of email strings
            subject=f"DCRC Contact Form: {subject}",
            plain_text_content=text_content,
            html_content=html_content
        )
        
        # Add CC recipient if configured
        if email_cc:
            mail.add_cc(email_cc)
            logger.info(f"CC recipient added: {email_cc}")
        
        # Set reply-to as tuple
        mail.reply_to = (email, name)
        
        # Send via SendGrid API
        logger.info(f"Sending email via SendGrid API from {name} ({email}) to {email_to}")
        logger.debug(f"From: {email_from}, To: {email_to}, Subject: DCRC Contact Form: {subject}")
        
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(mail)
        
        logger.info(f"SendGrid API response status: {response.status_code}")
        logger.debug(f"SendGrid API response headers: {dict(response.headers)}")
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"✅ Contact email sent successfully via SendGrid API (status: {response.status_code})")
            return True, None
        else:
            error_body = response.body.decode('utf-8') if response.body else "No error body"
            logger.error(f"SendGrid API returned status {response.status_code}: {error_body}")
            return False, f"SendGrid API error: {response.status_code} - {error_body}"
            
    except Exception as e:
        import traceback
        logger.error(f"Error sending email via SendGrid API: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, f"Failed to send email: {str(e)}"


def send_contact_email_smtp(name, email, phone, subject, message):
    """
    Send contact form email via SMTP (SendGrid SMTP on port 2525 or other providers)
    
    Args:
        name: Sender's name
        email: Sender's email
        phone: Sender's phone (optional)
        subject: Email subject category
        message: Email message content
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        # Get SMTP configuration from environment
        smtp_host = os.getenv('SMTP_HOST', 'smtp.sendgrid.net')
        smtp_port = int(os.getenv('SMTP_PORT', '2525'))
        smtp_user = os.getenv('SMTP_USER', 'apikey')  # SendGrid uses 'apikey' as username
        smtp_pass = os.getenv('SMTP_PASS') or os.getenv('SENDGRID_API_KEY')  # Can use API key as password
        email_from = os.getenv('EMAIL_FROM')
        email_to = os.getenv('EMAIL_TO')
        email_cc = os.getenv('EMAIL_CC')  # Optional CC recipient
        
        # Validate SMTP configuration
        if not all([smtp_pass, email_from, email_to]):
            logger.error("Missing SMTP configuration in environment variables")
            return False, "Email service not configured"
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = email_from
        msg['To'] = email_to
        if email_cc:
            msg['Cc'] = email_cc
            logger.info(f"CC recipient added: {email_cc}")
        msg['Reply-To'] = email
        msg['Subject'] = f"DCRC Contact Form: {subject}"
        
        # Plain text version
        text_content = f"""
New Contact Form Submission

Name: {name}
Email: {email}
Phone: {phone or 'Not provided'}
Subject: {subject}

Message:
{message}

---
This email was sent from the DCRC contact form at dcrc.ac.tz
        """
        
        # HTML version
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #285F68; margin-bottom: 20px;">New Contact Form Submission</h2>
        
        <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 10px 0;"><strong>Name:</strong> {name}</p>
            <p style="margin: 10px 0;"><strong>Email:</strong> <a href="mailto:{email}" style="color: #285F68;">{email}</a></p>
            <p style="margin: 10px 0;"><strong>Phone:</strong> {phone or 'Not provided'}</p>
            <p style="margin: 10px 0;"><strong>Subject:</strong> {subject}</p>
        </div>
        
        <div style="margin: 20px 0;">
            <h3 style="color: #285F68; margin-bottom: 10px;">Message:</h3>
            <div style="background: #ffffff; padding: 15px; border-left: 4px solid #285F68; line-height: 1.6; color: #333;">
                {message.replace(chr(10), '<br>')}
            </div>
        </div>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        
        <p style="color: #666; font-size: 12px; margin: 10px 0;">
            This email was sent from the DCRC contact form at <a href="https://dcrc.ac.tz" style="color: #285F68;">dcrc.ac.tz</a>
        </p>
        
        <p style="color: #666; font-size: 12px; margin: 10px 0;">
            You can reply directly to this email to respond to {name}.
        </p>
    </div>
</body>
</html>
        """
        
        # Attach both versions
        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Connect to SMTP server and send email
        logger.info(f"Connecting to SMTP server: {smtp_host}:{smtp_port}")
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.set_debuglevel(0)  # Set to 1 for debugging
            server.starttls()  # Upgrade to secure connection
            
            logger.info(f"Logging in as: {smtp_user}")
            server.login(smtp_user, smtp_pass)
            
            # Prepare recipients list (To + CC)
            recipients = [email_to]
            if email_cc:
                recipients.append(email_cc)
            
            logger.info(f"Sending email from {email_from} to {email_to}" + (f" (CC: {email_cc})" if email_cc else ""))
            server.send_message(msg, to_addrs=recipients)
            
        logger.info(f"✅ Contact email sent successfully via SMTP from {name} ({email})")
        return True, None
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {str(e)}")
        return False, "Email authentication failed"
    
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {str(e)}")
        return False, "Failed to send email"
    
    except Exception as e:
        logger.error(f"Unexpected error sending contact email via SMTP: {str(e)}")
        return False, "An error occurred while sending email"


def send_contact_email(name, email, phone, subject, message):
    """
    Send contact form email - tries SendGrid API first, falls back to SMTP
    
    Args:
        name: Sender's name
        email: Sender's email
        phone: Sender's phone (optional)
        subject: Email subject category
        message: Email message content
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    # Try SendGrid API first (recommended - uses HTTPS, works on DigitalOcean)
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
    
    if sendgrid_api_key and SENDGRID_AVAILABLE:
        logger.info("Attempting to send email via SendGrid API...")
        success, error = send_contact_email_sendgrid_api(name, email, phone, subject, message)
        if success:
            return True, None
        logger.warning(f"SendGrid API failed: {error}, trying SMTP fallback...")
    
    # Fallback to SMTP (SendGrid SMTP on port 2525 or other providers)
    logger.info("Attempting to send email via SMTP...")
    return send_contact_email_smtp(name, email, phone, subject, message)


@contact_bp.route('/api/contact', methods=['POST'])
def submit_contact_form():
    """
    Public endpoint to handle contact form submissions
    No authentication required
    
    Request Body:
    {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+255 655 123 456",  // optional
        "subject": "general",
        "message": "I would like to inquire..."
    }
    
    Response:
    {
        "status": "success",
        "message": "Email sent successfully"
    }
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        # Validate data
        is_valid, error_message = validate_contact_data(data)
        if not is_valid:
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 400
        
        # Extract fields
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        
        # Log the contact attempt
        logger.info(f"📧 Contact form submission from: {name} ({email}), Subject: {subject}")
        
        # Send email
        success, error = send_contact_email(name, email, phone, subject, message)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Email sent successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': error or 'Failed to send email'
            }), 500
    
    except Exception as e:
        logger.error(f"Error processing contact form: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while processing your request'
        }), 500


@contact_bp.route('/api/contact/test', methods=['GET'])
def test_smtp_config():
    """
    Test endpoint to verify email configuration
    Returns configuration status (without exposing credentials)
    """
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    email_from = os.getenv('EMAIL_FROM')
    email_to = os.getenv('EMAIL_TO')
    email_cc = os.getenv('EMAIL_CC')
    
    # Check SendGrid API configuration
    sendgrid_configured = bool(sendgrid_api_key and email_from and email_to)
    
    # Check SMTP configuration
    smtp_configured = bool(smtp_pass and email_from and email_to)
    
    config_status = {
        'sendgrid_api': 'configured' if sendgrid_api_key else 'missing',
        'email_from': 'configured' if email_from else 'missing',
        'email_to': 'configured' if email_to else 'missing',
        'email_cc': 'configured' if email_cc else 'not set (optional)',
        'smtp_host': 'configured' if smtp_host else 'missing (optional)',
        'smtp_port': 'configured' if smtp_port else 'missing (optional)',
        'smtp_user': 'configured' if smtp_user else 'missing (optional)',
        'smtp_pass': 'configured' if smtp_pass else 'missing (optional)',
    }
    
    # At least one method must be configured
    any_configured = sendgrid_configured or smtp_configured
    
    method = 'SendGrid API' if sendgrid_configured else ('SMTP' if smtp_configured else 'None')
    
    return jsonify({
        'status': 'success' if any_configured else 'incomplete',
        'message': f'Email service configured ({method})' if any_configured else 'Email service not configured',
        'method': method,
        'sendgrid_available': SENDGRID_AVAILABLE,
        'configuration': config_status
    }), 200 if any_configured else 500

