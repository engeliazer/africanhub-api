# Nginx Configuration for Static Files

## Problem
Images uploaded to `/storage/instructors/` and `/storage/testimonials/` are not accessible because nginx isn't configured to serve static files from the storage directory.

## Solution
Add a location block to serve static files from the storage directory.

## Nginx Configuration

Add this to your nginx server block for `api.ocpac.dcrc.ac.tz`:

```nginx
server {
    listen 443 ssl http2;
    server_name api.ocpac.dcrc.ac.tz;
    
    # ... existing SSL and other configurations ...
    
    # API routes
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' $cors_origin always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range,Range' always;
        add_header 'Access-Control-Allow-Credentials' 'true' always;
        
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' $cors_origin;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }
    
    # NEW: Serve static files from storage directory
    location /storage/ {
        alias /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/;
        
        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";
        
        # Cache static files for 1 year
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Enable gzip compression
        gzip on;
        gzip_vary on;
        gzip_min_length 1024;
        gzip_types
            text/plain
            text/css
            text/xml
            text/javascript
            application/javascript
            application/xml+rss
            application/json
            image/svg+xml;
        
        # Handle missing files
        try_files $uri $uri/ =404;
    }
    
    # ... rest of your configuration ...
}
```

## Steps to Apply

1. **Edit the nginx configuration:**
   ```bash
   sudo nano /etc/nginx/sites-available/api.ocpac.dcrc.ac.tz
   ```

2. **Add the `/storage/` location block** as shown above

3. **Test the configuration:**
   ```bash
   sudo nginx -t
   ```

4. **Reload nginx:**
   ```bash
   sudo systemctl reload nginx
   ```

5. **Create the storage directory structure:**
   ```bash
   sudo mkdir -p /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/instructors
   sudo mkdir -p /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/testimonials
   sudo chown -R www-data:www-data /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/
   sudo chmod -R 755 /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/
   ```

## Alternative: Flask Static File Route

If you prefer to handle this in Flask instead of nginx, add this route to your Flask app:

```python
from flask import send_from_directory
import os

@app.route('/storage/<path:filename>')
def serve_storage_file(filename):
    """Serve files from the storage directory"""
    try:
        storage_path = os.path.join(UPLOAD_FOLDER, '..')
        return send_from_directory(storage_path, filename)
    except FileNotFoundError:
        return "File not found", 404
```

## Testing

After applying the configuration, test the URLs:

```bash
# Test instructor image
curl -I https://api.ocpac.dcrc.ac.tz/storage/instructors/advocate-amiri-nyumile-sharifu-57a82e07.png

# Test testimonial image  
curl -I https://api.ocpac.dcrc.ac.tz/storage/testimonials/james-mwenda.jpg
```

## File Structure

The storage directory should look like this:

```
/var/www/ocpac/api.ocpac.dcrc.ac.tz/
├── storage/
│   ├── instructors/
│   │   ├── advocate-amiri-nyumile-sharifu-57a82e07.png
│   │   └── ...
│   ├── testimonials/
│   │   ├── james-mwenda.jpg
│   │   └── ...
│   └── materials/
│       └── ...
```

## Security Considerations

- The nginx configuration includes security headers
- Files are served with proper MIME types
- Caching is configured for performance
- Directory listing is disabled by default
