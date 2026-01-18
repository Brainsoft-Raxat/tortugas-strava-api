# Deployment Guide - Production Server

This guide covers deploying the Strava Platform application to any production server (DigitalOcean, AWS, etc.) with Docker Compose, nginx reverse proxy, and SSL certificates.

## Prerequisites

- Ubuntu 22.04 or later server (DigitalOcean droplet, AWS EC2, etc.)
- DNS A record pointing your domain to your server's IP address
- SSH access to your server
- Root or sudo access

## Initial Server Setup

### 1. Connect to your server

```bash
ssh your-server
```

### 2. Update system packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Install Docker and Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Log out and back in for group changes to take effect
exit
ssh your-server

# Verify installation
docker --version
docker compose version
```

### 4. Install Git

```bash
sudo apt install git -y
```

### 5. Set up firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

## Application Deployment

### 1. Clone repository

```bash
cd ~
git clone <your-repo-url> strava-platform
cd strava-platform/deploy
```

### 2. Create production .env file

```bash
cp env.example .env
nano .env
```

Fill in the following variables (replace with your actual values):

```env
# Domain Configuration
DOMAIN=your-domain.com
SSL_EMAIL=your-email@example.com

# Database
POSTGRES_USER=strava
POSTGRES_PASSWORD=<generate-strong-password>
POSTGRES_DB=strava_platform

# Strava API
STRAVA_CLIENT_ID=<your-client-id>
STRAVA_CLIENT_SECRET=<your-client-secret>
STRAVA_REDIRECT_URI=https://your-domain.com/auth/callback
STRAVA_VERIFY_TOKEN=<generate-random-token>
STRAVA_CLUB_ID=<your-club-id>

# Security
ADMIN_API_KEY=<generate-strong-api-key>

# Application
WEBHOOK_BASE_URL=https://your-domain.com
ENVIRONMENT=production
```

To generate secure tokens, you can use:
```bash
openssl rand -hex 32
```

### 3. Start the application (without SSL first)

```bash
docker compose -f docker-compose.prod.yml up -d
```

Check that containers are running:
```bash
docker compose -f docker-compose.prod.yml ps
```

### 4. Set up SSL certificates

The SSL setup script reads from your .env file:
```bash
./setup-ssl.sh
```

This will:
- Generate Let's Encrypt SSL certificates
- Configure nginx with HTTPS
- Set up automatic certificate renewal

### 5. Verify deployment

Visit your application (replace with your domain):
- http://your-domain.com (should redirect to HTTPS)
- https://your-domain.com/health (should show health status)
- https://your-domain.com/docs (FastAPI documentation)

## Ongoing Operations

### View logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f app
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Restart services

```bash
docker compose -f docker-compose.prod.yml restart app
```

### Update application

```bash
chmod +x deploy.sh
./deploy.sh
```

Or manually:
```bash
git pull
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

### Database backups

```bash
# Create backup
docker exec strava-platform-db pg_dump -U strava strava_platform > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker exec -i strava-platform-db psql -U strava strava_platform < backup_20260118_120000.sql
```

### Run database migrations manually

```bash
docker exec strava-platform-app alembic upgrade head
```

## Strava Webhook Setup

After deployment, register your webhook with Strava:

1. Get an access token for a user with appropriate permissions
2. Use the Strava API or run this inside the app container:

```bash
docker exec -it strava-platform-app python -c "
from src.strava.client import AsyncStravaClient
import asyncio

async def create_subscription():
    client = AsyncStravaClient(access_token='<your-token>')
    result = await client.create_webhook_subscription(
        client_id='<your-client-id>',
        client_secret='<your-client-secret>',
        callback_url='https://your-domain.com/webhooks/strava',
        verify_token='<your-verify-token>'
    )
    print(result)

asyncio.run(create_subscription())
"
```

## Monitoring

### Check resource usage

```bash
docker stats
```

### Check disk space

```bash
df -h
docker system df
```

### Clean up Docker resources

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (careful!)
docker volume prune
```

## Security Recommendations

1. Set up automatic security updates:
```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

2. Consider adding fail2ban for SSH protection:
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
```

3. Regularly update Docker images:
```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Container won't start

Check logs:
```bash
docker compose -f docker-compose.prod.yml logs app
```

### SSL certificate issues

Verify nginx can reach Let's Encrypt:
```bash
docker exec strava-platform-nginx curl -I http://letsencrypt.org
```

Manually renew certificates:
```bash
docker compose -f docker-compose.prod.yml run --rm certbot renew
```

### Database connection issues

Check postgres container:
```bash
docker exec strava-platform-db pg_isready -U strava
```

### Application errors

Check application logs:
```bash
docker compose -f docker-compose.prod.yml logs -f app
```

Enter container for debugging:
```bash
docker exec -it strava-platform-app /bin/bash
```

## Performance Tuning

For production use, consider:

1. Adjusting PostgreSQL settings in docker-compose.prod.yml
2. Adding Redis for caching (if needed)
3. Setting up monitoring with Prometheus/Grafana
4. Configuring nginx caching for static assets
5. Implementing log rotation

## Support

For issues, check:
- Application logs: `docker compose -f docker-compose.prod.yml logs app`
- Nginx logs: `docker compose -f docker-compose.prod.yml logs nginx`
- Database logs: `docker compose -f docker-compose.prod.yml logs postgres`
