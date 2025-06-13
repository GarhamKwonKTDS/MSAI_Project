#!/bin/bash
set -e

echo "🚀 Starting minimal Azure OpenAI deployment..."

# Configuration
RESOURCE_GROUP="rg-oss-chatbot-dev"
LOCATION="canadaeast"
TIMESTAMP=$(date +%m%d-%H%M)
OPENAI_SERVICE_NAME="openai-oss-${TIMESTAMP}"

echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  OpenAI Service: $OPENAI_SERVICE_NAME"
echo ""

# Step 1: Create Resource Group
echo "📁 Creating resource group..."
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

echo "✅ Resource group created"
echo ""

# Step 2: Create Azure OpenAI Service
echo "🤖 Creating Azure OpenAI Service..."
az cognitiveservices account create \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --location $LOCATION \
  --kind OpenAI \
  --sku S0 \
  --yes

echo "✅ OpenAI service created"
echo ""

# Step 3: Show the created resource
echo "📋 Verifying creation..."
az cognitiveservices account show \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --query "{name:name, provisioningState:properties.provisioningState, endpoint:properties.endpoint}" \
  --output table

echo ""
echo "🎉 Done! OpenAI service created successfully."
echo "Next step would be to deploy a model to this service."

# Step 4: Wait for service to be fully ready
echo ""
echo "⏳ Waiting 20 seconds for service to be fully ready..."
sleep 20

# Step 5: Deploy a model
echo ""
echo "🚀 Deploying GPT-4o-mini model..."
az cognitiveservices account deployment create \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --deployment-name "gpt-4o-mini" \
  --model-name "gpt-4o-mini" \
  --model-version "2024-07-18" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "GlobalStandard"

echo ""
echo "✅ Model deployment complete!"

# Step 6: Verify deployment
echo ""
echo "📋 Verifying model deployment..."
az cognitiveservices account deployment list \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --output table

echo ""
echo "🎉 All done! OpenAI service and model deployed successfully."

# Step 7: Get OpenAI credentials for later use
echo ""
echo "🔑 Getting OpenAI credentials..."
AZURE_OPENAI_KEY=$(az cognitiveservices account keys list \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --query "key1" \
  --output tsv)

AZURE_OPENAI_ENDPOINT=$(az cognitiveservices account show \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --query "properties.endpoint" \
  --output tsv)

echo "✅ Credentials retrieved"

# Step 8: Create Azure AI Search
echo ""
echo "🔍 Creating Azure AI Search service..."
SEARCH_SERVICE_NAME="search-oss-${TIMESTAMP}"

az search service create \
  --resource-group $RESOURCE_GROUP \
  --name $SEARCH_SERVICE_NAME \
  --location $LOCATION \
  --sku basic \
  --partition-count 1 \
  --replica-count 1

echo "✅ Search service created"

# Step 9: Wait for Search to be ready
echo ""
echo "⏳ Waiting for Search service to be ready..."
sleep 30

# Step 10: Get Search credentials
echo ""
echo "🔑 Getting Search credentials..."
SEARCH_KEY=$(az search admin-key show \
  --resource-group $RESOURCE_GROUP \
  --service-name $SEARCH_SERVICE_NAME \
  --query "primaryKey" \
  --output tsv)

SEARCH_ENDPOINT="https://${SEARCH_SERVICE_NAME}.search.windows.net"

echo "✅ Search credentials retrieved"

# Step 11: Summary
echo ""
echo "📋 Deployment Summary:"
echo "  OpenAI Service: $OPENAI_SERVICE_NAME"
echo "  OpenAI Endpoint: $AZURE_OPENAI_ENDPOINT"
echo "  Search Service: $SEARCH_SERVICE_NAME"
echo "  Search Endpoint: $SEARCH_ENDPOINT"
echo ""
echo "🎉 Core Azure services deployed successfully!"
echo "Next steps: App Service and code deployment"

# Step 12: Create App Service Plan
echo ""
echo "📱 Creating App Service Plan (Free tier)..."
APP_SERVICE_PLAN="plan-oss-${TIMESTAMP}"
APP_NAME="app-oss-${TIMESTAMP}"

az appservice plan create \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_PLAN \
  --location $LOCATION \
  --sku F1 \
  --is-linux

echo "✅ App Service Plan created"

# Step 13: Create Web App
echo ""
echo "🌐 Creating Web App..."
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $APP_NAME \
  --runtime "PYTHON:3.11"

echo "✅ Web App created"

# Step 14: Configure App Settings
echo ""
echo "⚙️ Configuring app settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings \
    AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT}" \
    AZURE_OPENAI_KEY="${AZURE_OPENAI_KEY}" \
    AZURE_OPENAI_MODEL="gpt-4o-mini" \
    AZURE_SEARCH_ENDPOINT="${SEARCH_ENDPOINT}" \
    AZURE_SEARCH_KEY="${SEARCH_KEY}" \
    AZURE_SEARCH_INDEX="oss-knowledge-base" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
    USE_AZURE_OPENAI="true"

# Set startup command
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"

echo "✅ App settings configured"

# Step 15: Deploy Application Code
echo ""
echo "📦 Preparing deployment package..."

# Create deployment directory
mkdir -p deployment
cd deployment

# Copy Flask app (assuming app.py is in parent directory)
if [ -f ../app.py ]; then
    cp ../app.py .
else
    echo "⚠️ app.py not found in parent directory!"
fi

# Create requirements.txt
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
EOF

# Create zip package
zip -r ../deployment.zip .
cd ..

echo "🚀 Deploying application..."
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --src deployment.zip

echo "✅ Application deployed"

# Step 16: Setup Knowledge Base
echo ""
echo "📚 Setting up knowledge base..."

# Create and activate virtual environment
echo "🐍 Setting up Python virtual environment..."
if command -v python3 &> /dev/null; then
    python3.13 -m venv venv
    source venv/bin/activate
    
    # Install required packages for knowledge base setup
    echo "📦 Installing required packages..."
    pip install azure-search-documents python-dotenv
    
    # Create temporary environment file for the setup script
    cat > .env << EOF
AZURE_SEARCH_ENDPOINT=${SEARCH_ENDPOINT}
AZURE_SEARCH_KEY=${SEARCH_KEY}
AZURE_SEARCH_INDEX=oss-knowledge-base
EOF
    
    # Run the knowledge base setup
    if [ -f setup_search_index.py ]; then
        echo "🚀 Running knowledge base setup..."
        python setup_search_index.py
    else
        echo "⚠️ setup_search_index.py not found!"
    fi
    
    # Deactivate virtual environment
    deactivate
    
    # Clean up venv
    echo "🧹 Cleaning up virtual environment..."
    rm -rf venv
else
    echo "⚠️ Python3 not found. Please install Python 3 to set up the knowledge base."
    echo "   You can manually run: python3 setup_search_index.py"
fi

# Step 17: Final Summary
APP_URL="https://${APP_NAME}.azurewebsites.net"

echo ""
echo "🎉 Deployment completed successfully!"
echo "================================"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo ""
echo "Azure OpenAI:"
echo "  Service: $OPENAI_SERVICE_NAME"
echo "  Endpoint: $AZURE_OPENAI_ENDPOINT"
echo "  Model: gpt-4o-mini"
echo ""
echo "Azure AI Search:"
echo "  Service: $SEARCH_SERVICE_NAME"
echo "  Endpoint: $SEARCH_ENDPOINT"
echo "  Index: oss-knowledge-base"
echo ""
echo "Web App:"
echo "  Name: $APP_NAME"
echo "  URL: $APP_URL"
echo "  Health Check: ${APP_URL}/health"
echo ""

# Save deployment info
cat > deployment-info.json << EOF
{
  "app_url": "${APP_URL}",
  "resource_group": "${RESOURCE_GROUP}",
  "azure_openai_endpoint": "${AZURE_OPENAI_ENDPOINT}",
  "search_endpoint": "${SEARCH_ENDPOINT}",
  "search_index": "oss-knowledge-base",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "📄 Deployment info saved to deployment-info.json"

echo ""
echo "🤖 Your OSS chatbot is ready!"
echo "Test it at: ${APP_URL}"