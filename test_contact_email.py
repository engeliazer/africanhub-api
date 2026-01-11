#!/usr/bin/env python3
"""
Test script for contact form email functionality
Run this to test SMTP configuration and email sending
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test 1: Check environment variables
print("=" * 60)
print("TEST 1: Environment Variables Check")
print("=" * 60)

required_vars = ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']
missing_vars = []

for var in required_vars:
    value = os.getenv(var)
    if value:
        # Mask sensitive values
        if 'PASS' in var:
            display_value = '*' * 8
        else:
            display_value = value
        print(f"✅ {var}: {display_value}")
    else:
        print(f"❌ {var}: NOT SET")
        missing_vars.append(var)

if missing_vars:
    print(f"\n❌ Missing variables: {', '.join(missing_vars)}")
    print("\nPlease add these to your .env file:")
    print("\nSMTP_HOST=smtp.zoho.com")
    print("SMTP_PORT=587")
    print("SMTP_USER=info@dcrc.ac.tz")
    print("SMTP_PASS=SomaCPA2025")
    print("EMAIL_FROM=info@dcrc.ac.tz")
    print("EMAIL_TO=engeliazer@gmail.com")
    sys.exit(1)

print("\n✅ All environment variables are set!")

# Test 2: Test SMTP connection
print("\n" + "=" * 60)
print("TEST 2: SMTP Connection Test")
print("=" * 60)

import smtplib

try:
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    
    print(f"Connecting to {smtp_host}:{smtp_port}...")
    
    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        print("✅ Connection established")
        
        print("Starting TLS...")
        server.starttls()
        print("✅ TLS started")
        
        print(f"Logging in as {smtp_user}...")
        server.login(smtp_user, smtp_pass)
        print("✅ Authentication successful")
    
    print("\n✅ SMTP connection test passed!")
    
except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ Authentication failed: {e}")
    print("Please check your SMTP_USER and SMTP_PASS credentials")
    sys.exit(1)
    
except smtplib.SMTPException as e:
    print(f"\n❌ SMTP error: {e}")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Connection error: {e}")
    sys.exit(1)

# Test 3: Send test email
print("\n" + "=" * 60)
print("TEST 3: Send Test Email")
print("=" * 60)

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    email_from = os.getenv('EMAIL_FROM')
    email_to = os.getenv('EMAIL_TO')
    
    # Create test message
    msg = MIMEMultipart('alternative')
    msg['From'] = email_from
    msg['To'] = email_to
    msg['Subject'] = "DCRC Contact Form - Test Email"
    
    text_content = """
This is a test email from the DCRC contact form system.

If you received this email, the SMTP configuration is working correctly!

Test Details:
- SMTP Host: smtp.zoho.com
- SMTP Port: 587
- From: info@dcrc.ac.tz
- To: engeliazer@gmail.com

---
This is an automated test email.
    """
    
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #285F68;">✅ DCRC Contact Form - Test Email</h2>
    
    <div style="background: #f0f9ff; padding: 20px; border-radius: 8px; border-left: 4px solid #285F68;">
        <p>This is a test email from the DCRC contact form system.</p>
        <p><strong>If you received this email, the SMTP configuration is working correctly!</strong></p>
    </div>
    
    <div style="margin: 20px 0;">
        <h3 style="color: #285F68;">Test Details:</h3>
        <ul>
            <li><strong>SMTP Host:</strong> smtp.zoho.com</li>
            <li><strong>SMTP Port:</strong> 587</li>
            <li><strong>From:</strong> info@dcrc.ac.tz</li>
            <li><strong>To:</strong> engeliazer@gmail.com</li>
        </ul>
    </div>
    
    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
    
    <p style="color: #666; font-size: 12px;">
        This is an automated test email from the DCRC contact form system.
    </p>
</body>
</html>
    """
    
    part1 = MIMEText(text_content, 'plain')
    part2 = MIMEText(html_content, 'html')
    msg.attach(part1)
    msg.attach(part2)
    
    # Send email
    print(f"Sending test email from {email_from} to {email_to}...")
    
    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    
    print(f"✅ Test email sent successfully!")
    print(f"\nCheck {email_to} for the test email.")
    print("(Don't forget to check spam folder if you don't see it)")
    
except Exception as e:
    print(f"\n❌ Failed to send test email: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nYour contact form email system is ready to use!")
print("\nNext steps:")
print("1. Deploy the backend changes")
print("2. Test the /api/contact endpoint")
print("3. Verify emails arrive at engeliazer@gmail.com")
print("\nTest endpoint:")
print("  curl -X POST http://localhost:5001/api/contact \\")
print("    -H 'Content-Type: application/json' \\")
print("    -d '{")
print('      "name": "Test User",')
print('      "email": "test@example.com",')
print('      "phone": "+255 655 123 456",')
print('      "subject": "general",')
print('      "message": "This is a test message"')
print("    }'")
print("\n" + "=" * 60)

