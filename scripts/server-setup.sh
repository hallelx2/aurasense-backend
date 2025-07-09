#!/bin/bash

# Server Setup Script for Digital Ocean VPS
# Run this ONCE on your new VPS to set it up

set -e

echo "🔧 Setting up server for Aurasense deployment..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install essential packages
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

# Install Docker
echo "🐳 Installing Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io

# Install Docker Compose
echo "🐙 Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Configure UFW firewall
echo "🔥 Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp  # Your app port
echo "y" | ufw enable

# Create project directory
echo "📁 Creating project directory..."
mkdir -p /var/www
chown -R $USER:$USER /var/www

# Install Certbot for SSL
echo "🔒 Installing Certbot for SSL..."
apt install -y certbot python3-certbot-nginx

# Create basic Nginx config
echo "🌐 Creating basic Nginx configuration..."
cat > /etc/nginx/sites-available/aurasense << 'EOF'
server {
    listen 80;
    server_name _;  # Replace with your domain

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/aurasense /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Check if port 80 is in use
if lsof -i :80 | grep -q LISTEN; then
    echo "⚠️  Warning: Port 80 is already in use. Nginx may not start."
fi

nginx -t
if systemctl is-active --quiet nginx; then
    echo "🔄 Reloading Nginx..."
    systemctl reload nginx
else
    echo "🚀 Starting Nginx..."
    systemctl start nginx
fi

# Create deployment user (optional)
echo "👤 Creating deployment user..."
useradd -m -s /bin/bash deploy || true
usermod -aG docker deploy || true

echo "✅ Server setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Update your domain DNS to point to this server's IP"
echo "2. Update /etc/nginx/sites-available/aurasense with your domain"
echo "3. Run: certbot --nginx -d yourdomain.com"
echo "4. Copy your .env.production file to your local machine"
echo "5. Run your deployment script: ./scripts/deploy.sh production"
