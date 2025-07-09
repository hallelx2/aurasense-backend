#!/bin/bash

# Deployment script for systemd-based Aurasense Backend
set -e

echo "🚀 Starting Aurasense Backend deployment..."

# Server configuration
SERVER="root@aurasense"
APP_DIR="/var/www/html/aurasense-backend"
SERVICE_NAME="aurasense-backend.service"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we can connect to server
print_status "Checking server connection..."
if ! ssh -o ConnectTimeout=5 $SERVER "echo 'Connected'" > /dev/null 2>&1; then
    print_error "Cannot connect to server $SERVER"
    exit 1
fi

# Backup current deployment
print_status "Creating backup..."
BACKUP_DIR="/var/backups/aurasense-backend/$(date +%Y%m%d_%H%M%S)"
ssh $SERVER "mkdir -p $BACKUP_DIR && cp -r $APP_DIR $BACKUP_DIR/"

# Stop the service
print_status "Stopping application service..."
ssh $SERVER "systemctl stop $SERVICE_NAME"

# Pull latest code
print_status "Pulling latest code..."
ssh $SERVER "cd $APP_DIR && git pull origin main"

# Update environment file if provided
if [ -f ".env" ]; then
    print_status "Uploading environment configuration..."
    scp .env $SERVER:$APP_DIR/.env
fi

# Install/update dependencies
print_status "Installing dependencies..."
ssh $SERVER "cd $APP_DIR && /root/.local/bin/uv sync"

# Start the service
print_status "Starting application service..."
ssh $SERVER "systemctl start $SERVICE_NAME"

# Wait for service to start
sleep 5

# Check service status
print_status "Checking service status..."
if ssh $SERVER "systemctl is-active $SERVICE_NAME" | grep -q "active"; then
    print_status "✅ Deployment successful!"

    # Show service status
    echo -e "\n${GREEN}Service Status:${NC}"
    ssh $SERVER "systemctl status $SERVICE_NAME --no-pager -l"

    # Show recent logs
    echo -e "\n${GREEN}Recent Logs:${NC}"
    ssh $SERVER "journalctl -u $SERVICE_NAME --no-pager -n 10"

else
    print_error "❌ Service failed to start!"

    # Show error logs
    echo -e "\n${RED}Error Logs:${NC}"
    ssh $SERVER "journalctl -u $SERVICE_NAME --no-pager -n 20"

    # Offer rollback
    echo -e "\n${YELLOW}Rolling back to previous version...${NC}"
    ssh $SERVER "systemctl stop $SERVICE_NAME && rm -rf $APP_DIR && mv $BACKUP_DIR/aurasense-backend $APP_DIR && systemctl start $SERVICE_NAME"

    exit 1
fi

print_status "🎉 Deployment completed successfully!"
