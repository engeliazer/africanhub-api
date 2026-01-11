# 🚀 Deploy Contact Form to Production Server

## Current Status

✅ Code pushed to GitHub (commit: 7c62cf5)
✅ Local `.env` configured
❌ **Production server `.env` not configured**
❌ **Gunicorn not restarted**

---

## 🔧 Fix the Production Server

Follow these steps **on the server**:

### Step 1: SSH to Server

```bash
ssh dcrc@142.93.95.32
```

### Step 2: Navigate to Project Directory

```bash
cd /var/www/api.online.dcrc.ac.tz
```

### Step 3: Pull Latest Code

```bash
git pull origin main
```

You should see:
```
From https://github.com/engeliazer/ocpac-api
   a474c46..7c62cf5  main -> main
Updating a474c46..7c62cf5
...
```

### Step 4: Add SMTP Configuration to `.env`

```bash
nano .env
```

**Add these lines at the end of the file:**

```env
# Email/SMTP Configuration (Contact Form)
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USER=info@dcrc.ac.tz
SMTP_PASS=SomaCPA2025
EMAIL_FROM=info@dcrc.ac.tz
EMAIL_TO=engeliazer@gmail.com
```

**Save and exit:**
- Press `Ctrl+X`
- Press `Y` (to confirm)
- Press `Enter`

### Step 5: Verify Configuration

```bash
tail -7 .env
```

You should see the SMTP configuration lines.

### Step 6: Restart Gunicorn

```bash
sudo systemctl restart gunicorn-api
```

### Step 7: Check Service Status

```bash
sudo systemctl status gunicorn-api
```

Should show: `Active: active (running)`

### Step 8: Test SMTP Configuration

```bash
curl -X GET http://localhost/api/contact/test --unix-socket /var/www/api.online.dcrc.ac.tz/api.sock
```

**Expected response:**
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

### Step 9: Test Email Sending (from server)

```bash
curl -X POST http://localhost/api/contact \
  --unix-socket /var/www/api.online.dcrc.ac.tz/api.sock \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+255123456789",
    "subject": "general",
    "message": "This is a test message from production server"
  }'
```

**Expected response:**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

### Step 10: Test from Your Local Machine

Exit SSH and test from your Mac:

```bash
curl -X POST https://api.online.dcrc.ac.tz/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hamis Eliazer",
    "email": "engeliazer@gmail.com",
    "phone": "0755344162",
    "subject": "enrollment",
    "message": "Nakuja"
  }'
```

**Expected response:**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

### Step 11: Check Your Email

Check **engeliazer@gmail.com** for the test email from **info@dcrc.ac.tz**.

---

## 🐛 Troubleshooting

### If Service Won't Start

```bash
# Check error logs
sudo journalctl -u gunicorn-api -n 50

# Check for Python errors
sudo journalctl -u gunicorn-api | grep -i "error\|traceback"
```

### If Configuration Test Fails

```bash
# Verify .env file
cat .env | grep -E "SMTP|EMAIL"

# Should show:
# SMTP_HOST=smtp.zoho.com
# SMTP_PORT=587
# SMTP_USER=info@dcrc.ac.tz
# SMTP_PASS=SomaCPA2025
# EMAIL_FROM=info@dcrc.ac.tz
# EMAIL_TO=engeliazer@gmail.com
```

### If Email Sending Fails

```bash
# Watch logs in real-time
sudo journalctl -u gunicorn-api -f

# Then send test request from another terminal
# Check logs for error messages
```

### Common Issues

| Error | Solution |
|-------|----------|
| "Email service not configured" | `.env` missing SMTP vars or Gunicorn not restarted |
| "Authentication failed" | Check SMTP_USER and SMTP_PASS are correct |
| "Connection timeout" | Check firewall allows outbound port 587 |
| 500 Internal Server Error | Check Gunicorn logs for Python errors |

---

## 📋 Quick Checklist

- [ ] SSH to server (142.93.95.32)
- [ ] `cd /var/www/api.online.dcrc.ac.tz`
- [ ] `git pull origin main`
- [ ] `nano .env` - Add SMTP configuration
- [ ] `sudo systemctl restart gunicorn-api`
- [ ] `curl -X GET http://localhost/api/contact/test --unix-socket ...` - Test config
- [ ] Send test email via curl
- [ ] Check engeliazer@gmail.com
- [ ] Test from frontend at dcrc.ac.tz

---

## 🎉 Success Indicators

✅ SMTP config test returns `"status": "success"`
✅ Test email returns `"message": "Email sent successfully"`
✅ Email arrives in engeliazer@gmail.com inbox
✅ Contact form works from dcrc.ac.tz website

---

## 📞 Need Help?

Run this command on the server to get detailed diagnostics:

```bash
echo "=== Gunicorn Status ===" && \
sudo systemctl status gunicorn-api --no-pager && \
echo "" && \
echo "=== SMTP Configuration ===" && \
cat .env | grep -E "SMTP|EMAIL" && \
echo "" && \
echo "=== Recent Logs ===" && \
sudo journalctl -u gunicorn-api -n 20 --no-pager
```

This will show you everything you need to diagnose the issue.

