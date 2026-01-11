# 🚀 SendGrid Setup Guide - Contact Form Email

## ✅ Code Implementation Complete!

The contact form now supports **SendGrid API** (recommended) and **SendGrid SMTP** (fallback). SendGrid uses HTTPS (port 443) which works perfectly on DigitalOcean!

---

## 📋 Quick Setup (5 Minutes)

### Step 1: Sign Up for SendGrid (Free)

1. Go to: **https://signup.sendgrid.com/**
2. Click **"Start for Free"**
3. Fill out the form:
   - **Email:** engeliazer@gmail.com (or your email)
   - **Password:** (create a secure password)
   - **Company:** DCRC (Dar es Salaam Centre for Research and Consultancy)
   - **Website:** dcrc.ac.tz
4. Verify your email address
5. Complete the onboarding (takes 2 minutes)

**Free Tier:** 100 emails/day forever! ✅

---

### Step 2: Create API Key

1. **Log in to SendGrid:** https://app.sendgrid.com/
2. Go to **Settings** → **API Keys** (left sidebar)
3. Click **"Create API Key"**
4. **Name:** `DCRC Contact Form`
5. **Permissions:** Select **"Full Access"** (or "Mail Send" only)
6. Click **"Create & View"**
7. **⚠️ IMPORTANT:** Copy the API key immediately! You won't be able to see it again.

**Example API Key:** `SG_KEY_REDACTED_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

### Step 3: Verify Sender Identity (Required)

SendGrid requires you to verify who you're sending emails from:

#### Option A: Single Sender Verification (Easiest - 2 minutes)

1. Go to **Settings** → **Sender Authentication** → **Single Sender Verification**
2. Click **"Create New Sender"**
3. Fill out the form:
   - **From Email Address:** info@dcrc.ac.tz
   - **From Name:** DCRC Contact Form
   - **Reply To:** engeliazer@gmail.com
   - **Company Address:** (your address)
   - **City:** Dar es Salaam
   - **Country:** Tanzania
4. Click **"Create"**
5. **Check your email** (info@dcrc.ac.tz) for verification link
6. Click the verification link

**✅ Done!** You can now send emails from info@dcrc.ac.tz

#### Option B: Domain Authentication (Better - 10 minutes)

If you want to send from any email on your domain:

1. Go to **Settings** → **Sender Authentication** → **Domain Authentication**
2. Click **"Authenticate Your Domain"**
3. Enter: `dcrc.ac.tz`
4. Follow the DNS setup instructions
5. Add the DNS records to your domain provider
6. Wait for verification (usually 5-10 minutes)

---

### Step 4: Add API Key to Server

**SSH to your server:**

```bash
ssh dcrc@142.93.95.32
cd /var/www/api.online.dcrc.ac.tz
nano .env
```

**Add these lines to `.env`:**

```env
# SendGrid Configuration (Primary - Uses HTTPS, works on DigitalOcean)
SENDGRID_API_KEY=SG_KEY_REDACTED_your-api-key-here

# Email Configuration
EMAIL_FROM=info@dcrc.ac.tz
EMAIL_TO=engeliazer@gmail.com

# Optional: SendGrid SMTP (Fallback - uses port 2525)
# SMTP_HOST=smtp.sendgrid.net
# SMTP_PORT=2525
# SMTP_USER=apikey
# SMTP_PASS=SG_KEY_REDACTED_your-api-key-here
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

---

### Step 5: Install SendGrid Library

```bash
# Activate virtual environment
source venv/bin/activate

# Install SendGrid
pip install sendgrid==6.11.0

# Or install all requirements
pip install -r requirements.txt
```

---

### Step 6: Restart Gunicorn

```bash
sudo systemctl restart gunicorn-api
sudo systemctl status gunicorn-api
```

---

### Step 7: Test Configuration

```bash
curl -X GET http://localhost/api/contact/test --unix-socket /var/www/api.online.dcrc.ac.tz/api.sock
```

**Expected response:**
```json
{
  "status": "success",
  "message": "Email service configured (SendGrid API)",
  "method": "SendGrid API",
  "sendgrid_available": true,
  "configuration": {
    "sendgrid_api": "configured",
    "email_from": "configured",
    "email_to": "configured",
    ...
  }
}
```

---

### Step 8: Test Email Sending

```bash
curl -X POST http://localhost/api/contact \
  --unix-socket /var/www/api.online.dcrc.ac.tz/api.sock \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+255123456789",
    "subject": "general",
    "message": "Testing SendGrid integration!"
  }'
```

**Expected response:**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

**Check engeliazer@gmail.com** for the test email! 📧

---

## 🎯 How It Works

1. **Primary Method:** SendGrid API (HTTPS - port 443)
   - ✅ Always works (no port blocking)
   - ✅ Better deliverability
   - ✅ Faster
   - ✅ Recommended by DigitalOcean

2. **Fallback Method:** SendGrid SMTP (port 2525)
   - ✅ Works if API fails
   - ✅ Uses port 2525 (allowed by DigitalOcean)
   - ✅ Same API key as password

---

## 📊 SendGrid Dashboard

Monitor your email sending:

- **Dashboard:** https://app.sendgrid.com/
- **Activity:** See all sent emails
- **Statistics:** Open rates, clicks, etc.
- **Free Tier:** 100 emails/day

---

## 🐛 Troubleshooting

### "Email service not configured"

**Check:**
```bash
# Verify API key is set
cat .env | grep SENDGRID_API_KEY

# Should show:
# SENDGRID_API_KEY=SG_KEY_REDACTED_xxxxxxxxxxxxx
```

**Fix:** Add `SENDGRID_API_KEY` to `.env` and restart Gunicorn

---

### "SendGrid API error: 403"

**Cause:** Sender not verified or API key doesn't have permissions

**Fix:**
1. Verify sender email in SendGrid dashboard
2. Check API key has "Mail Send" permission
3. Create new API key with full access

---

### "SendGrid API error: 401"

**Cause:** Invalid API key

**Fix:**
1. Verify API key in `.env` is correct
2. Check for extra spaces or quotes
3. Create new API key if needed

---

### Email Not Received

**Check:**
1. **Spam folder** - Check engeliazer@gmail.com spam
2. **SendGrid Activity** - Go to SendGrid dashboard → Activity
3. **Logs:**
```bash
sudo journalctl -u gunicorn-api -f | grep -i "sendgrid\|email"
```

---

## ✅ Success Checklist

- [ ] SendGrid account created
- [ ] API key created and copied
- [ ] Sender verified (info@dcrc.ac.tz)
- [ ] `SENDGRID_API_KEY` added to `.env`
- [ ] SendGrid library installed (`pip install sendgrid`)
- [ ] Gunicorn restarted
- [ ] Configuration test returns success
- [ ] Test email sent successfully
- [ ] Email received in engeliazer@gmail.com

---

## 🎉 You're Done!

Your contact form now uses SendGrid and will work perfectly on DigitalOcean! 

**Benefits:**
- ✅ Works immediately (no waiting for DigitalOcean approval)
- ✅ Better deliverability than regular SMTP
- ✅ Free tier: 100 emails/day
- ✅ Professional email service
- ✅ Dashboard to monitor emails
- ✅ No port blocking issues

---

## 📞 Need Help?

**SendGrid Support:**
- Documentation: https://docs.sendgrid.com/
- Support: https://support.sendgrid.com/

**Check Logs:**
```bash
sudo journalctl -u gunicorn-api -n 50 | grep -i "sendgrid\|contact\|email"
```

---

**Next:** Test your contact form at https://dcrc.ac.tz! 🚀

