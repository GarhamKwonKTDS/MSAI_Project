#!/bin/bash
set -e

echo "🚀 Deploying Chatbot Backend..."

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
    
    AZURE_OPENAI_ENDPOINT=$(jq -r '.openai.endpoint' "$SERVICES_CONFIG")
    AZURE_OPENAI_KEY=$(jq -r '.openai.key' "$SERVICES_CONFIG")
    SEARCH_ENDPOINT=$(jq -r '.search.endpoint' "$SERVICES_CONFIG")
    SEARCH_KEY=$(jq -r '.search.key' "$SERVICES_CONFIG")
    COSMOS_ENDPOINT=$(jq -r '.cosmos.endpoint' "$SERVICES_CONFIG")
    COSMOS_KEY=$(jq -r '.cosmos.key' "$SERVICES_CONFIG")
else
    RESOURCE_GROUP=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['resource_group'])")
    LOCATION=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['location'])")
    TIMESTAMP=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['timestamp'])")
    
    AZURE_OPENAI_ENDPOINT=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['openai']['endpoint'])")
    AZURE_OPENAI_KEY=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['openai']['key'])")
    SEARCH_ENDPOINT=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['search']['endpoint'])")
    SEARCH_KEY=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['search']['key'])")
    COSMOS_ENDPOINT=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['cosmos']['endpoint'])")
    COSMOS_KEY=$(python3 -c "import json; print(json.load(open('$SERVICES_CONFIG'))['cosmos']['key'])")
fi

# Load app configuration if exists
if [ -f "$APPS_CONFIG" ]; then
    if command -v jq &> /dev/null; then
        APP_SERVICE_PLAN=$(jq -r '.app_service_plan' "$APPS_CONFIG" 2>/dev/null || echo "")
        BACKEND_APP_NAME=$(jq -r '.chatbot.backend.name' "$APPS_CONFIG" 2>/dev/null || echo "")
    else
        APP_SERVICE_PLAN=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('app_service_plan', ''))" 2>/dev/null || echo "")
        BACKEND_APP_NAME=$(python3 -c "import json; d=json.load(open('$APPS_CONFIG')); print(d.get('chatbot', {}).get('backend', {}).get('name', ''))" 2>/dev/null || echo "")
    fi
fi

# Set defaults if not found
APP_SERVICE_PLAN="${APP_SERVICE_PLAN:-plan-oss-${TIMESTAMP}}"
BACKEND_APP_NAME="${BACKEND_APP_NAME:-backend-oss-${TIMESTAMP}}"

echo "✅ Configuration loaded"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  App Service Plan: $APP_SERVICE_PLAN"
echo "  Backend App Name: $BACKEND_APP_NAME"

# Check if source directory exists
if [ ! -d "chatbot_backend" ]; then
    echo "❌ Source directory 'chatbot_backend' not found!"
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
if az webapp show --name $BACKEND_APP_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "🗑️ Deleting existing app..."
    az webapp delete \
        --name $BACKEND_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --keep-empty-plan
    echo "✅ Existing app deleted"
    sleep 10  # Wait for deletion to complete
fi

# Create new web app
echo ""
echo "🌐 Creating Chatbot Backend Web App..."
az webapp create \
    --resource-group $RESOURCE_GROUP \
    --plan $APP_SERVICE_PLAN \
    --name $BACKEND_APP_NAME \
    --runtime "PYTHON:3.11"

echo "✅ Web App created"

# Configure app settings
echo ""
echo "⚙️ Configuring app settings..."
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $BACKEND_APP_NAME \
    --settings \
    AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT}" \
    AZURE_OPENAI_KEY="${AZURE_OPENAI_KEY}" \
    AZURE_OPENAI_MODEL="gpt-4o-mini" \
    AZURE_OPENAI_EMBEDDING_MODEL="text-embedding-3-small" \
    AZURE_SEARCH_ENDPOINT="${SEARCH_ENDPOINT}" \
    AZURE_SEARCH_KEY="${SEARCH_KEY}" \
    AZURE_SEARCH_INDEX="oss-knowledge-base" \
    AZURE_COSMOS_ENDPOINT="${COSMOS_ENDPOINT}" \
    AZURE_COSMOS_KEY="${COSMOS_KEY}" \
    AZURE_COSMOS_DATABASE="voc-analytics" \
    AZURE_COSMOS_TURNS_CONTAINER="turns" \
    AZURE_COSMOS_CONVERSATIONS_CONTAINER="conversations" \
    AZURE_COSMOS_STATISTICS_CONTAINER="statistics" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

# Set startup command
az webapp config set \
    --resource-group $RESOURCE_GROUP \
    --name $BACKEND_APP_NAME \
    --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"

echo "✅ App settings configured"

# Prepare and deploy code
echo ""
echo "📦 Preparing deployment package from source..."
TEMP_DIR="temp_chatbot_backend_$(date +%s)"
mkdir -p $TEMP_DIR

# Copy source code
cp -r chatbot_backend/* $TEMP_DIR/

# Create requirements.txt
cat > $TEMP_DIR/requirements.txt << EOF
flask==3.0.0
flask-cors==4.0.0
langchain>=0.1.17
langchain-openai>=0.1.6
langgraph>=0.0.37
azure-search-documents==11.4.0
azure-core==1.29.5
python-dotenv==1.0.0
gunicorn==21.2.0
openai>=1.55.3
httpx>=0.28
pydantic>=2.0.0
azure-cosmos==4.5.1
EOF

# Create deployment package
cd $TEMP_DIR
zip -r ../chatbot_backend_deploy.zip .
cd ..

echo "🚀 Deploying to Azure..."
az webapp deployment source config-zip \
    --resource-group $RESOURCE_GROUP \
    --name $BACKEND_APP_NAME \
    --src chatbot_backend_deploy.zip

# Cleanup
rm -rf $TEMP_DIR
rm chatbot_backend_deploy.zip

BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"

echo ""
echo "✅ Chatbot Backend deployed successfully!"
echo "================================"
echo "App Name: $BACKEND_APP_NAME"
echo "URL: $BACKEND_URL"
echo "Health Check: ${BACKEND_URL}/health"
echo ""
echo "🔍 To check logs:"
echo "   az webapp log tail --name $BACKEND_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "🔄 To restart:"
echo "   az webapp restart --name $BACKEND_APP_NAME --resource-group $RESOURCE_GROUP"