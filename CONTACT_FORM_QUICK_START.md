# Contact Form - Quick Start Guide

## 🎯 What's Been Implemented

A **public contact form endpoint** that sends emails via Zoho SMTP when users submit the contact form on dcrc.ac.tz (no login required).

## 📋 Files Created/Modified

1. ✅ `public/controllers/contact_controller.py` - Email sending logic
2. ✅ `app.py` - Blueprint registration
3. ✅ `test_contact_email.py` - Testing script
4. ✅ `ENV_SETUP.md` - Environment setup guide
5. ✅ `CONTACT_EMAIL_IMPLEMENTATION.md` - Full documentation

## 🚀 Quick Deployment (3 Steps)

### Step 1: Add SMTP Credentials to `.env`

On your server, edit the `.env` file:

```bash
cd /var/www/api.online.dcrc.ac.tz
nano .env
```

Add these lines:

```env
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USER=info@dcrc.ac.tz
SMTP_PASS=SomaCPA2025
EMAIL_FROM=info@dcrc.ac.tz
EMAIL_TO=engeliazer@gmail.com
```

Save and exit (Ctrl+X, Y, Enter)

### Step 2: Deploy Code

```bash
# Pull latest changes
git pull origin main

# Restart Gunicorn
sudo systemctl restart gunicorn-api
```

### Step 3: Test It

```bash
# Test configuration
curl -X GET https://api.online.dcrc.ac.tz/api/contact/test

# Expected: {"status":"success","message":"SMTP fully configured",...}
```

## ✅ That's It!

The contact form on dcrc.ac.tz will now send emails to engeliazer@gmail.com when users submit it.

## 🧪 Testing

### Test from Command Line:

```bash
curl -X POST https://api.online.dcrc.ac.tz/api/contact \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+255 655 123 456",
    "subject": "general",
    "message": "This is a test message"
  }'
```

### Test from Frontend:

1. Go to https://dcrc.ac.tz
2. Navigate to Contact page
3. Fill out the form
4. Submit
5. Check engeliazer@gmail.com for the email

## 📧 Email Details

- **From:** info@dcrc.ac.tz
- **To:** engeliazer@gmail.com
- **Reply-To:** User's email (for easy replies)
- **Format:** HTML + Plain text
- **Subject:** "DCRC Contact Form: {subject}"

## 🔍 Troubleshooting

### Check if SMTP is configured:

```bash
curl https://api.online.dcrc.ac.tz/api/contact/test
```

### Check Gunicorn logs:

```bash
sudo journalctl -u gunicorn-api -f | grep -i "contact\|email"
```

### Common Issues:

1. **"Email service not configured"**
   - Check `.env` file has all SMTP variables
   - Restart Gunicorn after adding variables

2. **"Email authentication failed"**
   - Verify SMTP_USER and SMTP_PASS are correct
   - Check for typos in credentials

3. **"Email not received"**
   - Check spam folder in engeliazer@gmail.com
   - Verify EMAIL_TO is correct
   - Check Zoho sending limits

## 📱 API Endpoints

### POST /api/contact
**Public endpoint** - No authentication required

**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+255 655 123 456",
  "subject": "general",
  "message": "I would like to inquire..."
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "message": "Failed to send email"
}
```

### GET /api/contact/test
**Test endpoint** - Check SMTP configuration

**Response:**
```json
{
  "status": "success",
  "message": "SMTP fully configured",
  "configuration": {
    "smtp_host": "configured",
    "smtp_port": "configured",
    "smtp_user": "configured",
    "smtp_pass": "configured",
    "email_from": "configured",
    "email_to": "configured"
  }
}
```

## 🎉 Done!

Your contact form is now fully functional and will send emails to engeliazer@gmail.com whenever someone contacts you through dcrc.ac.tz!

