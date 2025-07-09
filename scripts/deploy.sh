#!/bin/bash

# Aurasense Backend Deployment Script
# Usage: ./scripts/deploy.sh [environment]

set -e  # Exit on any error

# Configuration
ENVIRONMENT=${1:-production}
SERVER_USER="root"  # or your user
SERVER_HOST="aurasense"
PROJECT_DIR="/var/www/aurasense-backend"
REPO_URL="https://github.com/hallelx2/aurasense-backend.git"

echo "🚀 Starting deployment to $ENVIRONMENT environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run commands on server
run_on_server() {
    ssh $SERVER_USER@$SERVER_HOST "$1"
}

# Function to copy files to server
copy_to_server() {
    scp $1 $SERVER_USER@$SERVER_HOST:$2
}

echo -e "${YELLOW}📄 Step 1: Preparing environment file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found! Please create one first.${NC}"
    exit 1
fi

# Create deployment environment file
echo -e "${YELLOW}📝 Creating deployment environment file...${NC}"
cp .env .env.deployment

# Modify the deployment env file for Docker environment
echo -e "${YELLOW}🔧 Updating environment variables for Docker deployment...${NC}"

# Update NEO4J_HOST for Docker environment
sed -i.bak 's/NEO4J_HOST=localhost/NEO4J_HOST=neo4j/' .env.deployment

# Update REDIS_URL for Docker environment
sed -i.bak 's|REDIS_URL=redis://localhost:6379|REDIS_URL=redis://redis:6379|' .env.deployment

# Update GRAPHITI_HOST for Docker environment
sed -i.bak 's/GRAPHITI_HOST=localhost/GRAPHITI_HOST=graphiti/' .env.deployment

# Set environment to production
sed -i.bak 's/ENVIRONMENT=development/ENVIRONMENT=production/' .env.deployment

# Add production environment if not exists
if ! grep -q "ENVIRONMENT=" .env.deployment; then
    echo "ENVIRONMENT=production" >> .env.deployment
fi

# Clean up backup file
rm -f .env.deployment.bak

echo -e "${GREEN}✅ Deployment environment file created${NC}"

echo -e "${YELLOW}📋 Step 2: Backing up current deployment...${NC}"
run_on_server "
    if [ -d '$PROJECT_DIR' ]; then
        cp -r $PROJECT_DIR ${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)
    fi
"

echo -e "${YELLOW}📥 Step 3: Pulling latest code...${NC}"
run_on_server "
    if [ ! -d '$PROJECT_DIR' ]; then
        git clone $REPO_URL $PROJECT_DIR
    else
        cd $PROJECT_DIR
        git fetch origin
        git reset --hard origin/main
    fi
"

echo -e "${YELLOW}📄 Step 4: Copying environment file...${NC}"
copy_to_server ".env.deployment" "$PROJECT_DIR/.env"
echo -e "${GREEN}✅ Environment file copied to server${NC}"

echo -e "${YELLOW}🐳 Step 5: Building and starting services...${NC}"
run_on_server "
    cd $PROJECT_DIR
    docker compose down || true
    docker compose pull
    docker compose build --no-cache
    docker compose up -d
"

echo -e "${YELLOW}⏱️  Step 6: Waiting for services to start...${NC}"
sleep 30

echo -e "${YELLOW}🔍 Step 7: Health check...${NC}"
if run_on_server "curl -f http://localhost:8000/health > /dev/null 2>&1"; then
    echo -e "${GREEN}✅ Deployment successful! Services are healthy.${NC}"
else
    echo -e "${RED}❌ Health check failed. Check logs:${NC}"
    run_on_server "cd $PROJECT_DIR && docker compose logs --tail=50"
    exit 1
fi

echo -e "${YELLOW}🧹 Step 8: Cleanup old backups (keeping last 5)...${NC}"
run_on_server "
    cd /var/www
    ls -dt aurasense-backend_backup_* 2>/dev/null | tail -n +6 | xargs rm -rf
"

echo -e "${YELLOW}🗑️  Step 9: Cleaning up local deployment file...${NC}"
rm -f .env.deployment
echo -e "${GREEN}✅ Local cleanup completed${NC}"

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${GREEN}🌐 Your app should be running at: https://$SERVER_HOST${NC}"
echo -e "${YELLOW}💡 To check logs: ssh $SERVER_USER@$SERVER_HOST 'cd $PROJECT_DIR && docker compose logs -f'${NC}"
