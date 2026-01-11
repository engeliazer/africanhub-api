# Updated Nginx Configuration for Clean URLs

## Current Issue
- Files are stored in `/storage/uploads/instructors/` and `/storage/uploads/testimonials/`
- But we want clean URLs like `/storage/instructors/` and `/storage/testimonials/`

## Solution
Update the nginx configuration to map the clean URLs to the actual file locations.

## Updated Nginx Configuration

Replace the current `/storage/` location block with these specific location blocks:

```nginx
# Serve instructor images from clean URL
location /storage/instructors/ {
    alias /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/uploads/instructors/;
    
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

# Serve testimonial images from clean URL
location /storage/testimonials/ {
    alias /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/uploads/testimonials/;
    
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
```

## Steps to Apply

1. **Edit nginx configuration:**
   ```bash
   sudo nano /etc/nginx/sites-available/api.ocpac.dcrc.ac.tz
   ```

2. **Replace the current `/storage/` location block** with the two specific location blocks above

3. **Test the configuration:**
   ```bash
   sudo nginx -t
   ```

4. **Reload nginx:**
   ```bash
   sudo systemctl reload nginx
   ```

## Expected Results

After applying this configuration:

- ✅ `https://api.ocpac.dcrc.ac.tz/storage/instructors/cpa-charles-romani-kitungutu-bd80969e.png`
- ✅ `https://api.ocpac.dcrc.ac.tz/storage/instructors/advocate-amiri-nyumile-sharifu-57a82e07.png`
- ✅ `https://api.ocpac.dcrc.ac.tz/storage/testimonials/james-mwenda.jpg`

## Benefits

- **Clean URLs** - No `/uploads/` in the path
- **Better organization** - Separate locations for different file types
- **Future-proof** - Easy to add more storage locations
- **Same performance** - Direct nginx serving with caching
