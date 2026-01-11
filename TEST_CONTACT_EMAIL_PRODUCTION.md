# ✅ SMTP Configuration Verified - Now Test Email Sending

## Current Status

✅ Code deployed to production
✅ SMTP configuration loaded successfully
✅ All environment variables present
🧪 **Ready to test actual email sending**

---

## 🧪 Test Email Sending

### Test 1: Send Email from Server

Run this **on the server** (you're already SSH'd in):

```bash
curl -X POST http://localhost/api/contact \
  --unix-socket /var/www/api.online.dcrc.ac.tz/api.sock \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Test from Production Server",
    "email": "test@dcrc.ac.tz",
    "phone": "+255123456789",
    "subject": "general",
    "message": "This is a test email sent from the production server to verify SMTP functionality."
  }'
```

**Expected response:**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

---

### Test 2: Monitor Logs (Optional)

Open another terminal and watch the logs in real-time:

```bash
ssh dcrc@142.93.95.32
sudo journalctl -u gunicorn-api -f | grep -i "contact\|email"
```

Then run the curl command above in the first terminal. You should see log entries like:
- `📧 Contact form submission from: Test from Production Server`
- `✅ Contact email sent successfully`

---

### Test 3: Test from Your Local Machine

Exit the SSH session and run this **from your Mac**:

```bash
curl -X POST https://api.online.dcrc.ac.tz/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hamis Eliazer",
    "email": "engeliazer@gmail.com",
    "phone": "0755344162",
    "subject": "enrollment",
    "message": "Nakuja - Testing contact form from production API"
  }'
```

**Expected response:**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

---

### Test 4: Check Your Email

📧 **Check engeliazer@gmail.com inbox**

You should receive an email with:
- **From:** info@dcrc.ac.tz
- **Subject:** DCRC Contact Form: enrollment
- **Content:** Professional HTML email with your test message
- **Reply-To:** engeliazer@gmail.com (for easy replies)

**Don't see it?** Check your spam/junk folder!

---

### Test 5: Test from Frontend (Final Test)

1. Open browser and go to: **https://dcrc.ac.tz**
2. Navigate to the **Contact** page
3. Fill out the form:
   - Name: Your Name
   - Email: engeliazer@gmail.com
   - Phone: 0755344162
   - Subject: Select a subject
   - Message: Write a test message
4. Click **Submit**
5. You should see a success message
6. Check engeliazer@gmail.com for the email

---

## 🎯 Success Checklist

- [ ] Test 1: Server curl returns success
- [ ] Test 2: Logs show email sent successfully
- [ ] Test 3: External curl returns success
- [ ] Test 4: Email received in engeliazer@gmail.com
- [ ] Test 5: Frontend contact form works

---

## 📧 Email Sample

The email you receive will look like this:

```
Subject: DCRC Contact Form: enrollment

┌─────────────────────────────────────────┐
│  New Contact Form Submission            │
├─────────────────────────────────────────┤
│  Name: Hamis Eliazer                    │
│  Email: engeliazer@gmail.com            │
│  Phone: 0755344162                      │
│  Subject: enrollment                    │
├─────────────────────────────────────────┤
│  Message:                               │
│  Nakuja - Testing contact form from     │
│  production API                         │
└─────────────────────────────────────────┘

This email was sent from the DCRC contact form at dcrc.ac.tz
You can reply directly to this email to respond to Hamis Eliazer.
```

---

## 🐛 Troubleshooting

### If email sending fails:

1. **Check logs:**
```bash
sudo journalctl -u gunicorn-api -n 50 | grep -i "error\|smtp\|email"
```

2. **Test SMTP connection directly:**
```bash
# On server
cd /var/www/api.online.dcrc.ac.tz
source venv/bin/activate
python test_contact_email.py
```

3. **Check Zoho mail:**
- Verify the account isn't locked
- Check sending limits
- Ensure password hasn't been changed

### Common Issues:

| Issue | Solution |
|-------|----------|
| "Authentication failed" | Verify SMTP_PASS in .env is correct |
| "Connection timeout" | Check firewall allows outbound port 587 |
| Email not received | Check spam folder, verify EMAIL_TO |
| "Rate limit exceeded" | Wait a few minutes, Zoho may be throttling |

---

## 🎉 Next Steps

Once all tests pass:

1. ✅ Contact form is live and working
2. ✅ Emails will be sent to engeliazer@gmail.com
3. ✅ Users can contact you from dcrc.ac.tz
4. ✅ You can reply directly to user's email

**Optional enhancements:**
- Add rate limiting to prevent spam
- Create auto-reply email to users
- Store submissions in database
- Add admin dashboard to view submissions

---

## 📞 Support

If you encounter issues, run this diagnostic:

```bash
echo "=== SMTP Test ===" && \
curl -X GET http://localhost/api/contact/test --unix-socket /var/www/api.online.dcrc.ac.tz/api.sock && \
echo "" && echo "=== Recent Logs ===" && \
sudo journalctl -u gunicorn-api -n 20 --no-pager | grep -i "contact\|email\|error"
```

This will show configuration status and recent logs.

---

**Now run Test 1 above to send your first production email!** 📧✨

