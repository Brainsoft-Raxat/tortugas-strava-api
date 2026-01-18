#!/bin/bash
set -e

# Setup SSL certificates with Let's Encrypt
# This script should be run ONCE after initial deployment

# Load environment variables from .env file
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "Error: .env file not found!"
    echo "Please create a .env file with DOMAIN and SSL_EMAIL variables."
    exit 1
fi

# Check required variables
if [ -z "$DOMAIN" ]; then
    echo "Error: DOMAIN not set in .env file"
    exit 1
fi

if [ -z "$SSL_EMAIL" ]; then
    echo "Error: SSL_EMAIL not set in .env file"
    echo "Please add SSL_EMAIL=your-email@example.com to your .env file"
    exit 1
fi

echo "Setting up SSL certificates for $DOMAIN..."

# Create temporary nginx config for certificate generation
cat > /tmp/nginx-certbot.conf << EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
EOF

# Copy temporary config
docker cp /tmp/nginx-certbot.conf strava-platform-nginx:/etc/nginx/conf.d/default.conf

# Reload nginx
docker exec strava-platform-nginx nginx -s reload

# Wait a moment for nginx to reload
sleep 2

# Get certificate
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $SSL_EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

# Regenerate nginx config with domain substitution
docker exec strava-platform-nginx sh -c "envsubst '\$DOMAIN' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf"

# Reload nginx with SSL config
docker exec strava-platform-nginx nginx -s reload

echo "SSL certificates generated successfully!"
echo "Certificates will auto-renew every 12 hours via certbot container."
