#!/bin/bash
set -e

echo "🚀 Deploying Admin Frontend..."

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
        ADMIN_FRONTEND_APP_NAME=$(jq -r '.admin.frontend.name' "$APPS_CONFIG" 2>/dev/null || echo "")
        ADMIN_BACKEND_APP_NAME=$(jq -r '.admin.backend.name' "$APPS_CONFIG" 2>/dev/null || echo "")
    else
        APP_SERVICE_PLAN=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('app_service_plan', ''))" 2>/dev/null || echo "")
        ADMIN_FRONTEND_APP_NAME=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('admin', {}).get('frontend', {}).get('name', ''))" 2>/dev/null || echo "")
        ADMIN_BACKEND_APP_NAME=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('admin', {}).get('backend', {}).get('name', ''))" 2>/dev/null || echo "")
    fi
fi

# Set defaults if not found
APP_SERVICE_PLAN="${APP_SERVICE_PLAN:-plan-oss-${TIMESTAMP}}"
ADMIN_FRONTEND_APP_NAME="${ADMIN_FRONTEND_APP_NAME:-admin-frontend-oss-${TIMESTAMP}}"
ADMIN_BACKEND_APP_NAME="${ADMIN_BACKEND_APP_NAME:-admin-backend-oss-${TIMESTAMP}}"
ADMIN_BACKEND_URL="https://${ADMIN_BACKEND_APP_NAME}.azurewebsites.net"

echo "✅ Configuration loaded"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  App Service Plan: $APP_SERVICE_PLAN"
echo "  Admin Frontend App Name: $ADMIN_FRONTEND_APP_NAME"
echo "  Admin Backend URL: $ADMIN_BACKEND_URL"

# Check if source directory exists
if [ ! -d "admin_frontend" ]; then
    echo "❌ Source directory 'admin_frontend' not found!"
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
if az webapp show --name $ADMIN_FRONTEND_APP_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "🗑️ Deleting existing app..."
    az webapp delete \
        --name $ADMIN_FRONTEND_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --keep-empty-plan
    echo "✅ Existing app deleted"
    sleep 10  # Wait for deletion to complete
fi

# Create new web app
echo ""
echo "🌐 Creating Admin Frontend Web App..."
az webapp create \
    --resource-group $RESOURCE_GROUP \
    --plan $APP_SERVICE_PLAN \
    --name $ADMIN_FRONTEND_APP_NAME \
    --runtime "NODE:20-lts"

echo "✅ Web App created"

# Configure app settings
echo ""
echo "⚙️ Configuring app settings..."
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $ADMIN_FRONTEND_APP_NAME \
    --settings \
    API_BASE_URL="${ADMIN_BACKEND_URL}" \
    NODE_ENV="production" \
    PORT="5000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

echo "✅ App settings configured"

# Prepare and deploy code
echo ""
echo "📦 Preparing deployment package from source..."
TEMP_DIR="temp_admin_frontend_$(date +%s)"
mkdir -p $TEMP_DIR

# Copy source code
cp -r admin_frontend/* $TEMP_DIR/

# Ensure package.json exists
if [ ! -f "$TEMP_DIR/package.json" ]; then
    echo "⚠️ package.json not found in source, creating default..."
    cat > $TEMP_DIR/package.json << EOF
{
    "name": "oss-admin-frontend",
    "version": "1.0.0",
    "description": "OSS Admin Dashboard Frontend",
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
zip -r ../admin_frontend_deploy.zip .
cd ..

echo "🚀 Deploying to Azure..."
az webapp deployment source config-zip \
    --resource-group $RESOURCE_GROUP \
    --name $ADMIN_FRONTEND_APP_NAME \
    --src admin_frontend_deploy.zip

# Cleanup
rm -rf $TEMP_DIR
rm admin_frontend_deploy.zip

ADMIN_FRONTEND_URL="https://${ADMIN_FRONTEND_APP_NAME}.azurewebsites.net"

echo ""
echo "✅ Admin Frontend deployed successfully!"
echo "================================"
echo "App Name: $ADMIN_FRONTEND_APP_NAME"
echo "URL: $ADMIN_FRONTEND_URL"
echo "Connected to Backend: $ADMIN_BACKEND_URL"
echo ""
echo "🔍 To check logs:"
echo "   az webapp log tail --name $ADMIN_FRONTEND_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "🔄 To restart:"
echo "   az webapp restart --name $ADMIN_FRONTEND_APP_NAME --resource-group $RESOURCE_GROUP"