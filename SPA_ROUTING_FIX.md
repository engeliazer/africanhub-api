# SPA Routing Fix for dcrc.ac.tz

## Problem
- Direct access to `https://dcrc.ac.tz/instructors` shows 404
- Accessing from website menu works (client-side routing)
- This happens because the server doesn't know about frontend routes

## Solution
Configure nginx to serve `index.html` for all routes that don't correspond to actual files.

## Current nginx Configuration
```nginx
server {
    listen 443 ssl;
    server_name dcrc.ac.tz www.dcrc.ac.tz;

    ssl_certificate /etc/letsencrypt/live/dcrc.ac.tz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dcrc.ac.tz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root /var/www/dcrc.ac.tz/dist;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;  # This is the problem!
    }
}
```

## Fixed nginx Configuration
```nginx
server {
    listen 443 ssl;
    server_name dcrc.ac.tz www.dcrc.ac.tz;

    ssl_certificate /etc/letsencrypt/live/dcrc.ac.tz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dcrc.ac.tz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root /var/www/dcrc.ac.tz/dist;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ /index.html;  # This fixes it!
    }
}
```

## Steps to Fix

1. **Edit nginx configuration:**
   ```bash
   sudo nano /etc/nginx/sites-available/dcrc.ac.tz
   ```

2. **Change the location block:**
   ```nginx
   location / {
       try_files $uri $uri/ /index.html;
   }
   ```

3. **Test the configuration:**
   ```bash
   sudo nginx -t
   ```

4. **Reload nginx:**
   ```bash
   sudo systemctl reload nginx
   ```

## How It Works

- `try_files $uri $uri/ /index.html;` means:
  1. Try to serve the requested file (`$uri`)
  2. If not found, try to serve it as a directory (`$uri/`)
  3. If still not found, serve `/index.html` (fallback)

## Alternative: More Specific Configuration

If you want more control, you can use this configuration:

```nginx
location / {
    try_files $uri $uri/ @fallback;
}

location @fallback {
    rewrite ^.*$ /index.html last;
}
```

## Expected Results

After applying this fix:
- ✅ `https://dcrc.ac.tz/instructors` - Works on refresh
- ✅ `https://dcrc.ac.tz/about` - Works on refresh  
- ✅ `https://dcrc.ac.tz/contact` - Works on refresh
- ✅ All SPA routes work on direct access and refresh

## Additional Considerations

### For API Routes
If you have API routes that should return 404, make sure they're handled before the SPA fallback:

```nginx
# Handle API routes first (if any)
location /api/ {
    # Your API configuration here
    return 404;  # or proxy to API server
}

# SPA fallback for all other routes
location / {
    try_files $uri $uri/ /index.html;
}
```

### For Static Assets
Static assets (CSS, JS, images) will still be served normally because they exist as actual files.

## Testing

After applying the fix, test these scenarios:
1. Direct access to `https://dcrc.ac.tz/instructors`
2. Refresh the page on `/instructors`
3. Navigate to `/instructors` from the menu
4. Check browser developer tools for any 404 errors
