#!/bin/bash
set -e

echo "🚀 Starting Applications deployment (Part 2)..."

# Check for services config file
CONFIG_FILE="${1:-services-config.json}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Services configuration file not found: $CONFIG_FILE"
    echo "Please run ./deploy_services.sh first or provide path to config file"
    exit 1
fi

echo "📄 Loading configuration from: $CONFIG_FILE"

# Load configuration using jq or python
if command -v jq &> /dev/null; then
    # Use jq if available
    RESOURCE_GROUP=$(jq -r '.resource_group' "$CONFIG_FILE")
    LOCATION=$(jq -r '.location' "$CONFIG_FILE")
    TIMESTAMP=$(jq -r '.timestamp' "$CONFIG_FILE")
    
    # OpenAI settings
    AZURE_OPENAI_ENDPOINT=$(jq -r '.openai.endpoint' "$CONFIG_FILE")
    AZURE_OPENAI_KEY=$(jq -r '.openai.key' "$CONFIG_FILE")
    
    # Search settings
    SEARCH_ENDPOINT=$(jq -r '.search.endpoint' "$CONFIG_FILE")
    SEARCH_KEY=$(jq -r '.search.key' "$CONFIG_FILE")
    
    # Cosmos settings
    COSMOS_ENDPOINT=$(jq -r '.cosmos.endpoint' "$CONFIG_FILE")
    COSMOS_KEY=$(jq -r '.cosmos.key' "$CONFIG_FILE")
    COSMOS_ACCOUNT_NAME=$(jq -r '.cosmos.account_name' "$CONFIG_FILE")
else
    # Fallback to python
    echo "Using Python to parse config..."
    RESOURCE_GROUP=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['resource_group'])")
    LOCATION=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['location'])")
    TIMESTAMP=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['timestamp'])")
    
    AZURE_OPENAI_ENDPOINT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['openai']['endpoint'])")
    AZURE_OPENAI_KEY=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['openai']['key'])")
    
    SEARCH_ENDPOINT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['search']['endpoint'])")
    SEARCH_KEY=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['search']['key'])")
    
    COSMOS_ENDPOINT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['cosmos']['endpoint'])")
    COSMOS_KEY=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['cosmos']['key'])")
    COSMOS_ACCOUNT_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['cosmos']['account_name'])")
fi

echo "✅ Configuration loaded"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo ""

# Step 1: Create App Service Plan
echo "📱 Creating App Service Plan..."
APP_SERVICE_PLAN="plan-oss-${TIMESTAMP}"

az appservice plan create \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_PLAN \
  --location $LOCATION \
  --sku B1 \
  --is-linux

echo "✅ App Service Plan created"

# Step 2: Deploy Chatbot Backend
echo ""
echo "🌐 Creating Chatbot Backend..."
BACKEND_APP_NAME="backend-oss-${TIMESTAMP}"

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $BACKEND_APP_NAME \
  --runtime "PYTHON:3.11"

echo "⚙️ Configuring chatbot backend settings..."
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

az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $BACKEND_APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"

# Deploy chatbot backend code
echo "📦 Deploying chatbot backend..."
mkdir -p temp_deployment
cd temp_deployment

if [ -d ../chatbot_backend ]; then
    cp -r ../chatbot_backend/* .
else
    echo "⚠️ chatbot_backend directory not found!"
fi

cat > requirements.txt << EOF
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

zip -r ../chatbot_backend.zip .
cd ..
rm -rf temp_deployment

az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $BACKEND_APP_NAME \
  --src chatbot_backend.zip

rm chatbot_backend.zip
echo "✅ Chatbot Backend deployed"

# Step 3: Deploy Chatbot Frontend
echo ""
echo "🌐 Creating Chatbot Frontend..."
FRONTEND_APP_NAME="frontend-oss-${TIMESTAMP}"

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $FRONTEND_APP_NAME \
  --runtime "NODE:20-lts"

echo "⚙️ Configuring chatbot frontend settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $FRONTEND_APP_NAME \
  --settings \
    API_BASE_URL="https://${BACKEND_APP_NAME}.azurewebsites.net" \
    NODE_ENV="production" \
    PORT="5000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

# Deploy chatbot frontend code
echo "📦 Deploying chatbot frontend..."
mkdir -p temp_deployment
cd temp_deployment

if [ -d ../chatbot_frontend ]; then
    cp -r ../chatbot_frontend/* .
else
    echo "⚠️ chatbot_frontend directory not found!"
fi

zip -r ../chatbot_frontend.zip .
cd ..
rm -rf temp_deployment

az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $FRONTEND_APP_NAME \
  --src chatbot_frontend.zip

rm chatbot_frontend.zip
echo "✅ Chatbot Frontend deployed"

# Step 4: Deploy Admin Backend
echo ""
echo "🌐 Creating Admin Backend..."
ADMIN_BACKEND_APP_NAME="admin-backend-oss-${TIMESTAMP}"

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $ADMIN_BACKEND_APP_NAME \
  --runtime "PYTHON:3.11"

echo "⚙️ Configuring admin backend settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_BACKEND_APP_NAME \
  --settings \
    AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT}" \
    AZURE_OPENAI_KEY="${AZURE_OPENAI_KEY}" \
    AZURE_OPENAI_MODEL="gpt-4o-mini" \
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

az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_BACKEND_APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"

# Deploy admin backend code
echo "📦 Deploying admin backend..."
mkdir -p temp_deployment
cd temp_deployment

if [ -d ../admin_backend ]; then
    cp -r ../admin_backend/* .
else
    echo "⚠️ admin_backend directory not found!"
fi

cat > requirements.txt << EOF
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

zip -r ../admin_backend.zip .
cd ..
rm -rf temp_deployment

az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_BACKEND_APP_NAME \
  --src admin_backend.zip

rm admin_backend.zip
echo "✅ Admin Backend deployed"

# Step 5: Deploy Admin Frontend
echo ""
echo "🌐 Creating Admin Frontend..."
ADMIN_FRONTEND_APP_NAME="admin-frontend-oss-${TIMESTAMP}"

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $ADMIN_FRONTEND_APP_NAME \
  --runtime "NODE:20-lts"

echo "⚙️ Configuring admin frontend settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_FRONTEND_APP_NAME \
  --settings \
    API_BASE_URL="https://${ADMIN_BACKEND_APP_NAME}.azurewebsites.net" \
    NODE_ENV="production" \
    PORT="5000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

# Deploy admin frontend code
echo "📦 Deploying admin frontend..."
mkdir -p temp_deployment
cd temp_deployment

if [ -d ../admin_frontend ]; then
    cp -r ../admin_frontend/* .
else
    echo "⚠️ admin_frontend directory not found!"
fi

zip -r ../admin_frontend.zip .
cd ..
rm -rf temp_deployment

az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_FRONTEND_APP_NAME \
  --src admin_frontend.zip

rm admin_frontend.zip
echo "✅ Admin Frontend deployed"

# Step 7: Save apps configuration
echo ""
echo "💾 Saving apps configuration..."

BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"
FRONTEND_URL="https://${FRONTEND_APP_NAME}.azurewebsites.net"
ADMIN_BACKEND_URL="https://${ADMIN_BACKEND_APP_NAME}.azurewebsites.net"
ADMIN_FRONTEND_URL="https://${ADMIN_FRONTEND_APP_NAME}.azurewebsites.net"

cat > apps-config.json << EOF
{
  "resource_group": "${RESOURCE_GROUP}",
  "app_service_plan": "${APP_SERVICE_PLAN}",
  "chatbot": {
    "backend": {
      "name": "${BACKEND_APP_NAME}",
      "url": "${BACKEND_URL}"
    },
    "frontend": {
      "name": "${FRONTEND_APP_NAME}",
      "url": "${FRONTEND_URL}"
    }
  },
  "admin": {
    "backend": {
      "name": "${ADMIN_BACKEND_APP_NAME}",
      "url": "${ADMIN_BACKEND_URL}"
    },
    "frontend": {
      "name": "${ADMIN_FRONTEND_APP_NAME}",
      "url": "${ADMIN_FRONTEND_URL}"
    }
  },
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "✅ Apps configuration saved to apps-config.json"

# Summary
echo ""
echo "🎉 Applications deployment completed!"
echo "================================"
echo "Resource Group: $RESOURCE_GROUP"
echo ""
echo "Chatbot Services:"
echo "  Backend: $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
echo ""
echo "Admin Services:"
echo "  Backend: $ADMIN_BACKEND_URL"
echo "  Frontend: $ADMIN_FRONTEND_URL"
echo ""
echo "📄 Configuration saved to: apps-config.json"
echo ""
echo "🧹 To clean up apps later:"
echo "   ./cleanup_apps.sh"