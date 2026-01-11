#!/bin/bash
# Verify SendGrid setup on server

set -e

APP_DIR="/var/www/api.online.dcrc.ac.tz"
ENV_FILE="$APP_DIR/.env"

echo "=== Checking SendGrid Configuration ==="
echo ""

# Check if SENDGRID_API_KEY exists in .env
if grep -q "^SENDGRID_API_KEY=" "$ENV_FILE"; then
    echo "✅ SENDGRID_API_KEY found in .env"
    echo "Value: $(grep '^SENDGRID_API_KEY=' "$ENV_FILE" | cut -d'=' -f2 | cut -c1-10)..."
else
    echo "❌ SENDGRID_API_KEY NOT found in .env"
    echo ""
    echo "Adding it now..."

    # Ask for the key securely (won't echo on screen)
    read -s -p "Enter SENDGRID_API_KEY: " SENDGRID_API_KEY
    echo ""
    if [ -z "$SENDGRID_API_KEY" ]; then
        echo "ERROR: SENDGRID_API_KEY is empty. Aborting."
        exit 1
    fi

    cd "$APP_DIR"
    {
      echo ""
      echo "# SendGrid Configuration"
      echo "SENDGRID_API_KEY=$SENDGRID_API_KEY"
    } >> "$ENV_FILE"

    echo "✅ Added SENDGRID_API_KEY to .env"
fi

echo ""
echo "=== Checking SendGrid Library ==="
cd "$APP_DIR"
source venv/tivate
if python -c "import sendgrid" 2>/dev/null; then
    echo "✅ SendGrid library installed"
else
    echo "❌ SendGrid library NOT installed"
    echo "Installing now..."
    pip install sendgrid==6.11.0
    echo "✅ SendGrid library installed"
fi

echo ""
echo "=== Restarting Gunicorn ==="
sudo systemctl restart gunicorn-api
sleep 2
echo "✅ Gunicorn restarted"

echo ""
echo "=== Testing Configurationrl -X GET http://localhost/api/contact/test --unix-socket "$APP_DIR/api.sock"

echo ""
echo "=== Done! ==="

