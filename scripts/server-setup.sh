#!/bin/bash

# Server Setup Script for Digital Ocean VPS
# Run this ONCE on your new VPS to set it up

set -e

echo "🔧 Setting up server for Aurasense deployment..."

# Update system
if [ -f /var/log/aurasense-system-updated ]; then
    echo "📦 System packages already updated. Skipping."
else
    echo "📦 Updating system packages..."
    apt update && apt upgrade -y
    touch /var/log/aurasense-system-updated
fi

# Install essential packages
if dpkg -l | grep -q nginx && dpkg -l | grep -q ufw && dpkg -l | grep -q htop; then
    echo "🛠️ Essential packages already installed. Skipping."
else
    echo "🛠️ Installing essential packages..."
    apt install -y \
        curl \
        wget \
        git \
        nginx \
        ufw \
        htop \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release
fi

# Install Docker
if command -v docker >/dev/null 2>&1; then
    echo "🐳 Docker already installed. Skipping."
else
    echo "🐳 Installing Docker..."
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io
fi

# Install Docker Compose
if command -v docker-compose >/dev/null 2>&1; then
    echo "🐙 Docker Compose already installed. Skipping."
else
    echo "🐙 Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Start and enable Docker
if systemctl is-active --quiet docker; then
    echo "🐳 Docker service already running. Skipping."
else
    systemctl start docker
    systemctl enable docker
fi

# Configure UFW firewall
if ufw status | grep -q "Status: active"; then
    echo "🔥 UFW firewall already configured. Skipping."
else
    echo "🔥 Configuring firewall..."
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8000/tcp  # Your app port
    echo "y" | ufw enable
fi

# Create project directory
if [ -d /var/www ]; then
    echo "📁 Project directory already exists. Skipping."
else
    echo "📁 Creating project directory..."
    mkdir -p /var/www
    chown -R $USER:$USER /var/www
fi

# Install Certbot for SSL
if command -v certbot >/dev/null 2>&1; then
    echo "🔒 Certbot already installed. Skipping."
else
    echo "🔒 Installing Certbot for SSL..."
    apt install -y certbot python3-certbot-nginx
fi

# Always overwrite Nginx config
echo "🌐 Writing Nginx config for teepon.tech ..."
cat > /etc/nginx/sites-available/aurasense << 'EOF'
# HTTP: Redirect all to HTTPS
server {
    listen 80;
    server_name teepon.tech www.teepon.tech;
    return 301 https://$host$request_uri;
}

# HTTPS: Main app
server {
    listen 443 ssl;
    server_name teepon.tech www.teepon.tech;

    ssl_certificate /etc/letsencrypt/live/teepon.tech/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/teepon.tech/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Redirect /scalar/ to /scalar
    location = /scalar/ {
        return 301 /scalar;
    }

    # Proxy /scalar to backend /scalar
    location /scalar {
        proxy_pass http://localhost:8000/scalar;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy all other requests to backend
    location / {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/aurasense /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
if systemctl is-active --quiet nginx; then
    echo "🔄 Reloading Nginx..."
    systemctl reload nginx
else
    echo "🚀 Starting Nginx..."
    systemctl start nginx
fi

# Obtain/renew SSL certificate with Certbot
if ! certbot certificates | grep -q 'teepon.tech'; then
    echo "🔒 Obtaining SSL certificate for teepon.tech ..."
    certbot --nginx -d teepon.tech -d www.teepon.tech --non-interactive --agree-tos -m halleluyaholudele@gmail.com --redirect
else
    echo "🔒 SSL certificate for teepon.tech already exists. Renewing if needed ..."
    certbot renew --quiet
fi
nginx -t
systemctl reload nginx

# Create deployment user (optional)
if id "deploy" >/dev/null 2>&1; then
    echo "👤 Deployment user already exists. Skipping."
else
    echo "👤 Creating deployment user..."
    useradd -m -s /bin/bash deploy || true
    usermod -aG docker deploy || true
fi

echo "✅ Server setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Update your domain DNS to point to this server's IP"
echo "2. Update /etc/nginx/sites-available/aurasense with your domain"
echo "3. Run: certbot --nginx -d yourdomain.com"
echo "4. Copy your .env.production file to your local machine"
echo "5. Run your deployment script: ./scripts/deploy.sh production"
echo "\nREMINDER: After DNS is set up, run: sudo certbot --nginx -d teepon.tech -d www.teepon.tech to enable HTTPS."
echo "If you make manual changes to /etc/nginx/sites-available/aurasense, run: sudo nginx -t && sudo systemctl reload nginx"
