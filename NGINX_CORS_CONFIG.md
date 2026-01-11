# Nginx CORS Configuration Check

## If CORS was working before and now it's not...

The issue might be that nginx is stripping or not passing through CORS headers from the Flask app.

## Check Nginx Configuration

```bash
# On production server
cat /etc/nginx/sites-available/api.ocpac.dcrc.ac.tz
# or
cat /etc/nginx/sites-enabled/api.ocpac.dcrc.ac.tz
```

## What to Look For

Your nginx config should have something like this in the `location` block:

```nginx
location / {
    # Proxy settings
    proxy_pass http://unix:/var/www/ocpac/api.ocpac.dcrc.ac.tz/gunicorn.sock;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # IMPORTANT: These lines ensure CORS headers from Flask are passed through
    proxy_hide_header Access-Control-Allow-Origin;
    add_header Access-Control-Allow-Origin * always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, Authorization, X-Requested-With, X-CSRF-Token" always;
    add_header Access-Control-Allow-Credentials "true" always;
    add_header Access-Control-Expose-Headers "Content-Type, Content-Length, Content-Range, Accept-Ranges, X-New-Token, X-Token-Refreshed" always;
    
    # Handle OPTIONS preflight requests
    if ($request_method = 'OPTIONS') {
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization, X-Requested-With, X-CSRF-Token" always;
        add_header Access-Control-Max-Age 3600;
        add_header Content-Type text/plain;
        add_header Content-Length 0;
        return 204;
    }
}
```

## Quick Test

**Run this on production to check current nginx config:**

```bash
sudo nginx -T | grep -A 50 "server_name api.ocpac.dcrc.ac.tz"
```

## If Config Needs Updating

```bash
# Edit nginx config
sudo nano /etc/nginx/sites-available/api.ocpac.dcrc.ac.tz

# Test config
sudo nginx -t

# If test passes, reload nginx
sudo systemctl reload nginx
```

## Alternative: Check What's Actually Being Sent

Run this from your local machine to see what headers the server is actually returning:

```bash
curl -X OPTIONS https://api.ocpac.dcrc.ac.tz/api/auth/login \
  -H "Origin: https://app.ocpac.dcrc.ac.tz" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type, Authorization" \
  -v 2>&1 | grep -i "access-control"
```

This will show you exactly which CORS headers are being sent by the server.

## Send Me This Info

Please run these commands and send me the output:

1. **Check nginx config:**
```bash
sudo cat /etc/nginx/sites-available/api.ocpac.dcrc.ac.tz
```

2. **Test CORS headers:**
```bash
curl -X OPTIONS https://api.ocpac.dcrc.ac.tz/api/auth/login \
  -H "Origin: https://app.ocpac.dcrc.ac.tz" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type, Authorization" \
  -v 2>&1 | grep -E "(< |access-control|Access-Control)"
```

3. **Check if it's a Flask or nginx issue:**
```bash
# Test Flask app directly (bypassing nginx)
curl -X OPTIONS http://localhost:8000/api/auth/login \
  -H "Origin: https://app.ocpac.dcrc.ac.tz" \
  -v 2>&1 | grep -i "access-control"
```

This will tell us whether the problem is in Flask (our code) or nginx (server config).

