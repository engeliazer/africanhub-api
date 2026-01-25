# Environment Variables Setup

## Required Environment Variables

Add these to your `.env` file in the project root:

### Email/SMTP Configuration (Contact Form)

```env
# Email Configuration
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USER=info@dcrc.ac.tz
SMTP_PASS=SomaCPA2025
EMAIL_FROM=info@dcrc.ac.tz
EMAIL_TO=engeliazer@gmail.com
```

### Other Existing Variables

Make sure these are also in your `.env`:

```env
# Database
DATABASE_URL=mysql+pymysql://username:password@localhost/dbname

# JWT
JWT_SECRET_KEY=your-secret-key-here

# VdoCipher
VDOCIPHER_API_SECRET=your-vdocipher-api-secret

# File Access
FILE_ACCESS_SECRET=your-file-access-secret

# B2 Storage
B2_APPLICATION_KEY_ID=your-b2-key-id
B2_APPLICATION_KEY=your-b2-key
B2_BUCKET_NAME=your-bucket-name

# Redis (Celery)
REDIS_URL=redis://localhost:6379/0

# SMS (mShastra)
MSHASTRA_USER=AFRICANHUB
MSHASTRA_PWD=AfricanHub@2026
MSHASTRA_SENDER=AFRICANHUB
# Optional: override API URL (default https://mshastra.com/sendsms_api_json.aspx)
# MSHASTRA_API_URL=https://mshastra.com/sendsms_api_json.aspx

# Upload
UPLOAD_FOLDER=./storage/uploads
```

## Security Notes

⚠️ **IMPORTANT:**
1. NEVER commit `.env` to Git
2. Ensure `.env` is in `.gitignore`
3. Use different credentials for production and development
4. Rotate passwords regularly
5. Use environment-specific `.env` files for different deployments

## Testing SMTP Configuration

After adding the variables, test the configuration:

```bash
curl -X GET http://localhost:5001/api/contact/test
```

Expected response:
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

