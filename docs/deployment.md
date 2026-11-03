# Production Deployment Guide

This guide describes how to safely deploy the Housing Society Member & Vehicle Tracking System in a production environment.

## 1. Environment Configuration

Production environments must never use development settings. Configure the following in your production `.env` file:

```env
# Mandatory Django configuration
DJANGO_SECRET_KEY='<cryptographically-secure-random-key>'
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=society.yourdomain.com,10.0.0.10

# Database
DB_NAME=housing_society_db
DB_USER=housing_society_user
DB_PASSWORD='<strong-db-password>'
DB_HOST=127.0.0.1
DB_PORT=5432

# Production Security
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_SSL_REDIRECT=True
```

### Security Setting Verification
When `DJANGO_DEBUG=False`:
- `SECURE_BROWSER_XSS_FILTER = True` protects against reflected XSS attacks.
- `SECURE_CONTENT_TYPE_NOSNIFF = True` prevents MIME-sniffing.
- `X_FRAME_OPTIONS = "DENY"` blocks clickjacking attacks.
- `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` ensure authentication cookies are only transmitted over TLS/HTTPS.
- `SECURE_SSL_REDIRECT = True` redirects all plain HTTP requests to HTTPS.

---

## 2. Static Asset Collection

Offline static assets (Bootstrap 5.3.3 and Bootstrap Icons 1.11.3) are bundled locally inside `static/vendor/`.

In production, run:
```powershell
python manage.py collectstatic --noinput
```
This gathers all assets into `staticfiles/`, which must be served directly by Nginx or Apache.

---

## 3. Web Server & WSGI Configuration

Never run `manage.py runserver` in production.

### Linux (Gunicorn + Nginx)

1. **Install Gunicorn**:
   ```bash
   pip install gunicorn
   ```

2. **Systemd Service (`/etc/systemd/system/vts.service`)**:
   ```ini
   [Unit]
   Description=Housing Society VTS Gunicorn Daemon
   After=network.target

   [Service]
   User=society
   Group=www-data
   WorkingDirectory=/opt/HousingSocietyVTS
   ExecStart=/opt/HousingSocietyVTS/.venv/bin/gunicorn \
       --access-logfile /var/log/vts/access.log \
       --error-logfile /var/log/vts/error.log \
       --workers 3 \
       --bind 127.0.0.1:8000 \
       config.wsgi:application
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Nginx Reverse Proxy (`/etc/nginx/sites-available/vts`)**:
   ```nginx
   server {
       listen 80;
       server_name society.yourdomain.com;
       return 301 https://$host$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name society.yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/society.yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/society.yourdomain.com/privkey.pem;

       location /static/ {
           alias /opt/HousingSocietyVTS/staticfiles/;
           expires 30d;
           add_header Cache-Control "public, no-transform";
       }

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

### Windows (Waitress + IIS)

On Windows servers, run using Waitress:
```powershell
pip install waitress
python -m waitress --port=8000 config.wsgi:application
```
Use IIS with URL Rewrite and ARR (Application Request Routing) to forward requests from port 443 to port 8000.

---

## 4. Production Checklist

1. [ ] `.env` created with `DJANGO_DEBUG=False` and a generated 50+ character random `DJANGO_SECRET_KEY`.
2. [ ] PostgreSQL database created with dedicated, restricted user permissions.
3. [ ] `python manage.py migrate` executed cleanly.
4. [ ] `python manage.py setup_roles` executed to seed Admin, Guard, and Resident groups.
5. [ ] Initial administrative account created with `python manage.py createsuperuser`.
6. [ ] `python manage.py collectstatic --noinput` completed.
7. [ ] TLS/HTTPS certificate active and auto-renewing.
8. [ ] Scheduled task configured for visitor pass expiry:
   ```bash
   0 0 * * * /opt/HousingSocietyVTS/.venv/bin/python /opt/HousingSocietyVTS/manage.py expire_visitors
   ```
