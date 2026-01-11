# Contact Form Email Implementation Guide

## Frontend Implementation ✅

The frontend has been updated to:
- Call `POST /api/contact` endpoint with form data
- Show loading state while submitting
- Display success/error messages
- Disable button during submission

## Backend Implementation ✅ COMPLETED

The backend endpoint has been implemented in Flask to send emails using Zoho SMTP credentials.

### API Endpoint Specification

**Endpoint:** `POST /api/contact`

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+255 655 123 456",
  "subject": "general",
  "message": "I would like to inquire about CPA courses..."
}
```

**Success Response:**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Failed to send email"
}
```

## Backend Email Configuration

### Environment Variables (REQUIRED)

Store these securely in your backend `.env` file:

```env
# Email Configuration
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_SECURE=true
SMTP_USER=info@dcrc.ac.tz
SMTP_PASS=SomaCPA2025
EMAIL_FROM=info@dcrc.ac.tz
EMAIL_TO=engeliazer@gmail.com
```

⚠️ **IMPORTANT SECURITY NOTES:**
1. NEVER commit these credentials to Git
2. Add `.env` to `.gitignore`
3. Use environment variables only
4. Never expose credentials in frontend code

## Sample Backend Implementation

### Node.js/Express with Nodemailer

```javascript
// Install required packages:
// npm install nodemailer dotenv

const nodemailer = require('nodemailer');
const express = require('express');
require('dotenv').config();

const router = express.Router();

// Create transporter
const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  port: parseInt(process.env.SMTP_PORT),
  secure: process.env.SMTP_PORT === '465', // true for 465, false for other ports
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS
  }
});

// POST /api/contact endpoint
router.post('/contact', async (req, res) => {
  try {
    const { name, email, phone, subject, message } = req.body;

    // Validate required fields
    if (!name || !email || !subject || !message) {
      return res.status(400).json({
        status: 'error',
        message: 'Missing required fields'
      });
    }

    // Email content
    const mailOptions = {
      from: process.env.EMAIL_FROM, // info@dcrc.ac.tz
      to: process.env.EMAIL_TO,      // engeliazer@gmail.com
      replyTo: email,                 // User's email for easy reply
      subject: `DCRC Contact Form: ${subject}`,
      html: `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <h2 style="color: #285F68;">New Contact Form Submission</h2>
          
          <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Name:</strong> ${name}</p>
            <p><strong>Email:</strong> ${email}</p>
            <p><strong>Phone:</strong> ${phone || 'Not provided'}</p>
            <p><strong>Subject:</strong> ${subject}</p>
          </div>
          
          <div style="margin: 20px 0;">
            <h3 style="color: #285F68;">Message:</h3>
            <p style="line-height: 1.6; color: #333;">${message}</p>
          </div>
          
          <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
          
          <p style="color: #666; font-size: 12px;">
            This email was sent from the DCRC contact form at dcrc.ac.tz
          </p>
        </div>
      `,
      text: `
        New Contact Form Submission
        
        Name: ${name}
        Email: ${email}
        Phone: ${phone || 'Not provided'}
        Subject: ${subject}
        
        Message:
        ${message}
        
        ---
        This email was sent from the DCRC contact form at dcrc.ac.tz
      `
    };

    // Send email
    await transporter.sendMail(mailOptions);

    res.json({
      status: 'success',
      message: 'Email sent successfully'
    });

  } catch (error) {
    console.error('Error sending email:', error);
    res.status(500).json({
      status: 'error',
      message: 'Failed to send email'
    });
  }
});

module.exports = router;
```

### Python/Django Implementation

```python
# Install: pip install python-dotenv

import os
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(["POST"])
def contact(request):
    try:
        data = json.loads(request.body)
        
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone', 'Not provided')
        subject = data.get('subject')
        message = data.get('message')
        
        # Validate required fields
        if not all([name, email, subject, message]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            }, status=400)
        
        # Compose email
        email_subject = f"DCRC Contact Form: {subject}"
        email_body = f"""
        New Contact Form Submission
        
        Name: {name}
        Email: {email}
        Phone: {phone}
        Subject: {subject}
        
        Message:
        {message}
        
        ---
        This email was sent from the DCRC contact form at dcrc.ac.tz
        """
        
        # Send email
        send_mail(
            subject=email_subject,
            message=email_body,
            from_email=os.getenv('EMAIL_FROM'),
            recipient_list=[os.getenv('EMAIL_TO')],
            fail_silently=False,
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Email sent successfully'
        })
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to send email'
        }, status=500)

# settings.py configuration:
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('SMTP_HOST')
EMAIL_PORT = int(os.getenv('SMTP_PORT'))
EMAIL_USE_TLS = os.getenv('SMTP_PORT') == '587'
EMAIL_USE_SSL = os.getenv('SMTP_PORT') == '465'
EMAIL_HOST_USER = os.getenv('SMTP_USER')
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASS')
```

## Testing the Email Configuration

### Test Email Sending

```javascript
// Test script (test-email.js)
const nodemailer = require('nodemailer');

const transporter = nodemailer.createTransport({
  host: 'smtp.zoho.com',
  port: 587,
  secure: false,
  auth: {
    user: 'info@dcrc.ac.tz',
    pass: 'SomaCPA2025'
  }
});

transporter.sendMail({
  from: 'info@dcrc.ac.tz',
  to: 'engeliazer@gmail.com',
  subject: 'Test Email from DCRC',
  text: 'This is a test email to verify SMTP configuration.'
}, (error, info) => {
  if (error) {
    console.error('Error:', error);
  } else {
    console.log('Email sent:', info.messageId);
  }
});
```

Run: `node test-email.js`

## SMTP Configuration Details

### Zoho Mail Settings

**Outgoing (SMTP):**
- **Host:** smtp.zoho.com
- **Port:** 587 (recommended) or 465
- **Security:** TLS (587) or SSL (465)
- **Username:** info@dcrc.ac.tz
- **Password:** SomaCPA2025

**Email Flow:**
1. User fills out contact form
2. Frontend sends data to `POST /api/contact`
3. Backend receives request
4. Backend sends email via Zoho SMTP
5. Email arrives at engeliazer@gmail.com
6. Email sender shows as info@dcrc.ac.tz
7. Reply-to is set to user's email for easy response

## Deployment Checklist

- [ ] Add SMTP credentials to backend `.env` file
- [ ] Implement `/api/contact` endpoint
- [ ] Test email sending locally
- [ ] Deploy backend changes
- [ ] Test contact form on production
- [ ] Verify emails arrive at engeliazer@gmail.com
- [ ] Test reply-to functionality

## Troubleshooting

### Common Issues:

1. **"Authentication failed"**
   - Verify credentials are correct
   - Check if Zoho account has 2FA enabled
   - May need app-specific password

2. **"Connection timeout"**
   - Check firewall settings
   - Verify SMTP port is not blocked
   - Try alternate port (587 vs 465)

3. **"Email not received"**
   - Check spam folder
   - Verify recipient email (engeliazer@gmail.com)
   - Check Zoho sending limits

4. **"TLS/SSL errors"**
   - Ensure correct security settings for port
   - Port 587 = TLS
   - Port 465 = SSL

## Flask Implementation ✅ COMPLETED

The backend has been implemented in Flask with the following files:

### Files Created/Modified:

1. **`public/controllers/contact_controller.py`** - Contact form controller with email sending logic
2. **`app.py`** - Registered the `contact_bp` blueprint
3. **`test_contact_email.py`** - Test script to verify SMTP configuration
4. **`ENV_SETUP.md`** - Environment variables documentation

### Implementation Details:

```python
# public/controllers/contact_controller.py
- POST /api/contact - Send contact form email (public, no auth)
- GET /api/contact/test - Test SMTP configuration
```

### Features:

✅ Public endpoint (no authentication required)
✅ Email validation
✅ HTML and plain text email formats
✅ Reply-to set to user's email
✅ Professional email template
✅ Error handling and logging
✅ SMTP configuration test endpoint

## Next Steps

1. ✅ Backend endpoint implemented
2. **Add environment variables to `.env` file** (see ENV_SETUP.md)
3. **Test the email functionality**
4. **Deploy backend changes**
5. **Test contact form on production**

### Testing Locally

1. **Add SMTP credentials to `.env`:**
```env
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USER=info@dcrc.ac.tz
SMTP_PASS=SomaCPA2025
EMAIL_FROM=info@dcrc.ac.tz
EMAIL_TO=engeliazer@gmail.com
```

2. **Test SMTP configuration:**
```bash
python test_contact_email.py
```

3. **Test the endpoint:**
```bash
curl -X POST http://localhost:5001/api/contact \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+255 655 123 456",
    "subject": "general",
    "message": "I would like to inquire about CPA courses..."
  }'
```

4. **Check configuration status:**
```bash
curl -X GET http://localhost:5001/api/contact/test
```

### Deployment Steps

1. **Update `.env` on server:**
```bash
# SSH to server
ssh dcrc@142.93.95.32

# Navigate to project
cd /var/www/api.online.dcrc.ac.tz

# Edit .env file
nano .env

# Add SMTP configuration:
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USER=info@dcrc.ac.tz
SMTP_PASS=SomaCPA2025
EMAIL_FROM=info@dcrc.ac.tz
EMAIL_TO=engeliazer@gmail.com
```

2. **Deploy code:**
```bash
# Pull latest changes
git pull origin main

# Restart Gunicorn
sudo systemctl restart gunicorn-api

# Check logs
sudo journalctl -u gunicorn-api -f
```

3. **Test on production:**
```bash
# Test configuration
curl -X GET https://api.online.dcrc.ac.tz/api/contact/test

# Test contact form
curl -X POST https://api.online.dcrc.ac.tz/api/contact \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "subject": "general",
    "message": "Test message"
  }'
```

4. **Verify:**
- Check engeliazer@gmail.com for test email
- Test from frontend at dcrc.ac.tz
- Verify reply-to functionality

The frontend is now ready and will work once the backend is deployed! 🚀
