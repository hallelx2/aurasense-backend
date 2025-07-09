#!/bin/bash

# Environment Setup Script
# This helps you create a proper .env file for both local development and deployment

echo "🔧 Setting up environment file..."

# Check if .env already exists
if [ -f ".env" ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled. Your existing .env file is unchanged."
        exit 0
    fi
fi

# Create .env file
cat > .env << 'EOF'
# Environment
ENVIRONMENT=development

# Application
APP_NAME=Aurasense
DEBUG=true
LOG_LEVEL=INFO
SECRET_KEY=your-super-secure-secret-key-change-this

# Server (for local development)
HOST=0.0.0.0
PORT=8000

# CORS Configuration (for local development)
CORS_ORIGINS=http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=*
CORS_ALLOW_HEADERS=*

# Domain Configuration (will be updated for deployment)
PRODUCTION_DOMAIN=yourdomain.com
FRONTEND_URL=http://localhost:3000

# Neo4j Configuration (for local development)
NEO4J_USER=neo4j
NEO4J_PASSWORD=test1234
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687
NEO4J_HOST=localhost

# Redis Configuration (for local development)
REDIS_URL=redis://localhost:6379

# Graphiti Configuration (for local development)
GRAPHITI_HOST=localhost
GRAPHITI_PORT=8080

# External APIs (ADD YOUR REAL API KEYS HERE)
GROQ_API_KEY=your-groq-api-key
OPENAI_API_KEY=your-openai-api-key
GOOGLE_PLACES_API_KEY=your-google-places-api-key
FOURSQUARE_API_KEY=your-foursquare-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Cloud Storage (ADD YOUR REAL AWS CREDENTIALS HERE)
CLOUD_STORAGE_PROVIDER=aws
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
AUDIO_BUCKET_NAME=aurasense-audio-files
EOF

echo "✅ .env file created successfully!"
echo ""
echo "📝 IMPORTANT: Please edit .env and update the following:"
echo "   - SECRET_KEY (generate a secure random key)"
echo "   - API keys (GROQ_API_KEY, OPENAI_API_KEY, etc.)"
echo "   - AWS credentials (if using cloud storage)"
echo "   - PRODUCTION_DOMAIN (your actual domain)"
echo ""
echo "💡 Tips:"
echo "   - For local development: NEO4J_HOST=localhost"
echo "   - For deployment: Script will automatically change to NEO4J_HOST=neo4j"
echo "   - The deployment script will handle Docker-specific changes automatically"
echo ""
echo "🚀 You can now run:"
echo "   make dev-local    # For local development"
echo "   make deploy       # For deployment to server"
