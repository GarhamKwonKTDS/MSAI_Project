#!/bin/bash
set -e

echo "🚀 Deploying Chatbot Frontend..."

# Check for config files
SERVICES_CONFIG="${1:-services-config.json}"
APPS_CONFIG="${2:-apps-config.json}"

if [ ! -f "$SERVICES_CONFIG" ]; then
    echo "❌ Services configuration file not found: $SERVICES_CONFIG"
    echo "Usage: $0 [services-config.json] [apps-config.json]"
    exit 1
fi

echo "📄 Loading configuration..."

# Load services configuration
if command -v jq &> /dev/null; then
    RESOURCE_GROUP=$(jq -r '.resource_group' "$SERVICES_CONFIG")
    LOCATION=$(jq -r '.location' "$SERVICES_CONFIG")
    TIMESTAMP=$(jq -r '.timestamp' "$SERVICES_CONFIG")
else
    RESOURCE_GROUP=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['resource_group'])")
    LOCATION=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['location'])")
    TIMESTAMP=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['timestamp'])")
fi

# Load app configuration if exists
if [ -f "$APPS_CONFIG" ]; then
    if command -v jq &> /dev/null; then
        APP_SERVICE_PLAN=$(jq -r '.app_service_plan' "$APPS_CONFIG" 2>/dev/null || echo "")
        FRONTEND_APP_NAME=$(jq -r '.chatbot.frontend.name' "$APPS_CONFIG" 2>/dev/null || echo "")
        BACKEND_APP_NAME=$(jq -r '.chatbot.backend.name' "$APPS_CONFIG" 2>/dev/null || echo "")
    else
        APP_SERVICE_PLAN=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('app_service_plan', ''))" 2>/dev/null || echo "")
        FRONTEND_APP_NAME=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('chatbot', {}).get('frontend', {}).get('name', ''))" 2>/dev/null || echo "")
        BACKEND_APP_NAME=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('chatbot', {}).get('backend', {}).get('name', ''))" 2>/dev/null || echo "")
    fi
fi

# Set defaults if not found
APP_SERVICE_PLAN="${APP_SERVICE_PLAN:-plan-oss-${TIMESTAMP}}"
FRONTEND_APP_NAME="${FRONTEND_APP_NAME:-frontend-oss-${TIMESTAMP}}"
BACKEND_APP_NAME="${BACKEND_APP_NAME:-backend-oss-${TIMESTAMP}}"
BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"

echo "✅ Configuration loaded"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  App Service Plan: $APP_SERVICE_PLAN"
echo "  Frontend App Name: $FRONTEND_APP_NAME"
echo "  Backend URL: $BACKEND_URL"

# Check if source directory exists
if [ ! -d "chatbot_frontend" ]; then
    echo "❌ Source directory 'chatbot_frontend' not found!"
    exit 1
fi

# Check if app service plan exists, create if not
echo ""
echo "🔍 Checking App Service Plan..."
if ! az appservice plan show --name $APP_SERVICE_PLAN --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "📱 Creating App Service Plan..."
    az appservice plan create \
        --resource-group $RESOURCE_GROUP \
        --name $APP_SERVICE_PLAN \
        --location $LOCATION \
        --sku B1 \
        --is-linux
    echo "✅ App Service Plan created"
else
    echo "✅ App Service Plan exists"
fi

# Check if app exists and delete if it does
echo ""
echo "🔍 Checking if app exists..."
if az webapp show --name $FRONTEND_APP_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "🗑️ Deleting existing app..."
    az webapp delete \
        --name $FRONTEND_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --keep-empty-plan
    echo "✅ Existing app deleted"
    sleep 10  # Wait for deletion to complete
fi

# Create new web app
echo ""
echo "🌐 Creating Chatbot Frontend Web App..."
az webapp create \
    --resource-group $RESOURCE_GROUP \
    --plan $APP_SERVICE_PLAN \
    --name $FRONTEND_APP_NAME \
    --runtime "NODE:20-lts"

echo "✅ Web App created"

# Configure app settings
echo ""
echo "⚙️ Configuring app settings..."
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $FRONTEND_APP_NAME \
    --settings \
    API_BASE_URL="${BACKEND_URL}" \
    NODE_ENV="production" \
    PORT="5000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

echo "✅ App settings configured"

# Prepare and deploy code
echo ""
echo "📦 Preparing deployment package from source..."
TEMP_DIR="temp_chatbot_frontend_$(date +%s)"
mkdir -p $TEMP_DIR

# Copy source code
cp -r chatbot_frontend/* $TEMP_DIR/

# Ensure package.json exists
if [ ! -f "$TEMP_DIR/package.json" ]; then
    echo "⚠️ package.json not found in source, creating default..."
    cat > $TEMP_DIR/package.json << EOF
{
    "name": "oss-chatbot-frontend",
    "version": "1.0.0",
    "description": "OSS VoC 지원 챗봇 Frontend",
    "main": "server.js",
    "scripts": {
        "start": "node server.js"
    },
    "engines": {
        "node": ">=14.0.0"
    }
}
EOF
fi

# Create deployment package
cd $TEMP_DIR
zip -r ../chatbot_frontend_deploy.zip .
cd ..

echo "🚀 Deploying to Azure..."
az webapp deployment source config-zip \
    --resource-group $RESOURCE_GROUP \
    --name $FRONTEND_APP_NAME \
    --src chatbot_frontend_deploy.zip

# Cleanup
rm -rf $TEMP_DIR
rm chatbot_frontend_deploy.zip

FRONTEND_URL="https://${FRONTEND_APP_NAME}.azurewebsites.net"

echo ""
echo "✅ Chatbot Frontend deployed successfully!"
echo "================================"
echo "App Name: $FRONTEND_APP_NAME"
echo "URL: $FRONTEND_URL"
echo "Connected to Backend: $BACKEND_URL"
echo ""
echo "🔍 To check logs:"
echo "   az webapp log tail --name $FRONTEND_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "🔄 To restart:"
echo "   az webapp restart --name $FRONTEND_APP_NAME --resource-group $RESOURCE_GROUP"