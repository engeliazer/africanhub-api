#!/bin/bash
# Script to add SMTP configuration to .env file

ENV_FILE=".env"

echo "Adding SMTP configuration to $ENV_FILE..."

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating new .env file..."
    touch "$ENV_FILE"
fi

# Check if SMTP variables already exist
if grep -q "SMTP_HOST" "$ENV_FILE"; then
    echo "⚠️  SMTP variables already exist in .env"
    echo "Skipping to avoid duplicates."
    echo ""
    echo "If you need to update them, manually edit .env file:"
    echo "  nano .env"
    exit 0
fi

# Add SMTP configuration
echo "" >> "$ENV_FILE"
echo "# Email/SMTP Configuration (Contact Form)" >> "$ENV_FILE"
echo "SMTP_HOST=smtp.zoho.com" >> "$ENV_FILE"
echo "SMTP_PORT=587" >> "$ENV_FILE"
echo "SMTP_USER=info@dcrc.ac.tz" >> "$ENV_FILE"
echo "SMTP_PASS=SomaCPA2025" >> "$ENV_FILE"
echo "EMAIL_FROM=info@dcrc.ac.tz" >> "$ENV_FILE"
echo "EMAIL_TO=engeliazer@gmail.com" >> "$ENV_FILE"

echo "✅ SMTP configuration added to .env"
echo ""
echo "Configuration added:"
echo "  SMTP_HOST=smtp.zoho.com"
echo "  SMTP_PORT=587"
echo "  SMTP_USER=info@dcrc.ac.tz"
echo "  SMTP_PASS=********"
echo "  EMAIL_FROM=info@dcrc.ac.tz"
echo "  EMAIL_TO=engeliazer@gmail.com"
echo ""
echo "🔄 Please restart your Flask application for changes to take effect."

