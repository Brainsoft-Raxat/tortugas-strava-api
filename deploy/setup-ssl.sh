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
echo "Step 1: Obtaining SSL certificate from Let's Encrypt..."

# Get certificate (nginx is already running with HTTP-only config)
# Override entrypoint because the certbot container has a custom entrypoint for auto-renewal
docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot \
    certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $SSL_EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

echo "Step 2: Switching nginx to HTTPS configuration..."

# Switch nginx config to HTTPS version
docker exec strava-platform-nginx sh -c "envsubst '\$DOMAIN' < /etc/nginx/templates/https.conf.template > /etc/nginx/conf.d/default.conf"

# Reload nginx with SSL config
docker exec strava-platform-nginx nginx -s reload

echo ""
echo "✅ SSL certificates generated successfully!"
echo "✅ Nginx configured for HTTPS"
echo "✅ Certificates will auto-renew every 12 hours via certbot container"
echo ""
echo "Your site is now available at: https://$DOMAIN"
