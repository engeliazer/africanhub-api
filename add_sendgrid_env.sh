#!/bin/bash
# Script to add SendGrid configuration to .env file on server

set -e

ENV_FILE="/var/www/api.online.dcrc.ac.tz/.env"

echo "Adding SendGrid configuration to $ENV_FILE..."

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

# Check if SENDGRID_API_KEY already exists
if grep -q "^SENDGRID_API_KEY=" "$ENV_FILE"; then
    echo "SENDGRID_API_KEY already exists in .env"
    echo "To update it, manually edit the file:"
    echo "  nano $ENV_FILE"
    exit 0
fi

# Prompt for API key (silent)
echo ""
echo "Please enter your SendGrid API Key:"
echo "(It should start with 'SG' and be about 70 characters long)"
read -s -p "API Key: " API_KEY
echo ""

if [ -z "$API_KEY" ]; then
    echo "Error: API key cannot be empty"
    exit 1
fi

# Add SendGrid configuration
{
  echo ""
  echo "# SendGrid Configuration (Contact Form - Uses HTTPS, works on DigitalOcean)"
  echo "SENDGRID_API_KEY=$API_KEY"
} >> "$ENV_FILE"

echo ""
echo "SendGrid API key added to .env"
echo "Preview: $(echo "$API_KEY" | cut -c1-10)..."
echo ""
echo "Please restart Gunicorn for changes to take effect:"
echo "  sudo systemctl restart gunicorn-api"

