# Quick Start - Deploy to DigitalOcean

Deploy your Strava Platform app to any server with Docker support.

## Prerequisites

- A server (DigitalOcean droplet, AWS EC2, etc.) with Ubuntu 22.04 or later
- SSH access to your server
- A domain name with DNS A record pointing to your server's IP address

## Quick Deploy Steps

### 1. SSH into your server
```bash
ssh your-server
```

### 2. Run the server setup (first time only)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Install Git
sudo apt install git -y

# Setup firewall
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Log out and back in for docker group to take effect
exit
ssh your-server
```

### 3. Clone your repository
```bash
cd ~
git clone <your-repo-url> strava-platform
cd strava-platform/deploy
```

### 4. Create .env file
```bash
cp env.example .env
nano .env
```

Fill in all required values (see `.env` template below).

### 5. Start the application
```bash
docker compose -f docker-compose.prod.yml up -d
```

### 6. Set up SSL certificates
```bash
./setup-ssl.sh
```

### 7. Verify deployment
Visit: `https://your-domain.com/health`

## Environment Variables Template

Create a `.env` file in the `deploy/` directory with these variables:

```env
# Domain Configuration
DOMAIN=your-domain.com
SSL_EMAIL=your-email@example.com

# Database
POSTGRES_USER=strava
POSTGRES_PASSWORD=<generate-with: openssl rand -hex 32>
POSTGRES_DB=strava_platform

# Strava API
STRAVA_CLIENT_ID=<from-strava-api-settings>
STRAVA_CLIENT_SECRET=<from-strava-api-settings>
STRAVA_REDIRECT_URI=https://your-domain.com/auth/callback
STRAVA_VERIFY_TOKEN=<generate-with: openssl rand -hex 32>
STRAVA_CLUB_ID=<your-club-id>

# Security
ADMIN_API_KEY=<generate-with: openssl rand -hex 32>

# Application
WEBHOOK_BASE_URL=https://your-domain.com
ENVIRONMENT=production
```

Generate secure tokens with:
```bash
openssl rand -hex 32
```

## Common Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f app

# Restart app
docker compose -f docker-compose.prod.yml restart app

# Deploy updates
./deploy.sh

# Backup database
docker exec strava-platform-db pg_dump -U strava strava_platform > backup.sql
```

## Example: Your Specific Setup

If your domain is `tortugas.raxat.site` pointing to `165.227.129.44`:

```env
DOMAIN=tortugas.raxat.site
SSL_EMAIL=your-email@example.com
STRAVA_REDIRECT_URI=https://tortugas.raxat.site/auth/callback
WEBHOOK_BASE_URL=https://tortugas.raxat.site
# ... (other variables)
```

For complete documentation, see [DEPLOYMENT.md](./DEPLOYMENT.md)
