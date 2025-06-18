#!/bin/bash
set -e

echo "🚀 Starting minimal Azure OpenAI deployment..."

# Configuration (default: canadaeast)
LOCATION="australiaeast"
TIMESTAMP=$(date +%m%d-%H%M)
RESOURCE_GROUP="rg-oss-chatbot-dev-${TIMESTAMP}"
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

# Step 5.5: Deploy text-embedding-3-small model
echo ""
echo "🔤 Deploying text-embedding-3-small model..."
az cognitiveservices account deployment create \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --deployment-name "text-embedding-3-small" \
  --model-name "text-embedding-3-small" \
  --model-version "1" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "Standard"

echo "✅ Embedding model deployment complete!"

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

# Step 11a: Create Cosmos DB Account
echo ""
echo "🌍 Creating Cosmos DB account..."
COSMOS_ACCOUNT_NAME="cosmos-oss-${TIMESTAMP}"
COSMOS_LOCATION="westus3"  # Or try: northcentralus, westcentralus, southcentralus
echo "⚠️ Using $COSMOS_LOCATION for Cosmos DB due to capacity constraints"

az cosmosdb create \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT_NAME \
  --locations regionName=$COSMOS_LOCATION failoverPriority=0 isZoneRedundant=false \
  --default-consistency-level "Session"

echo "✅ Cosmos DB account created"

# Wait for Cosmos DB to be ready
echo ""
echo "⏳ Waiting for Cosmos DB to be ready..."
sleep 30

# Create database and container
echo ""
echo "📦 Creating Cosmos DB database and container..."
az cosmosdb sql database create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --name "voc-analytics"

az cosmosdb sql container create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --database-name "voc-analytics" \
  --name "turns" \
  --partition-key-path "/session_id" \
  --throughput 400

az cosmosdb sql container create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --database-name "voc-analytics" \
  --name "conversations" \
  --partition-key-path "/session_id" \
  --throughput 400

az cosmosdb sql container create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --database-name "voc-analytics" \
  --name "statistics" \
  --partition-key-path "/data" \
  --throughput 400

echo "✅ Cosmos DB database and container created"

# Get Cosmos DB connection details
echo ""
echo "🔑 Getting Cosmos DB credentials..."
COSMOS_ENDPOINT=$(az cosmosdb show \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT_NAME \
  --query "documentEndpoint" \
  --output tsv)

COSMOS_KEY=$(az cosmosdb keys list \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT_NAME \
  --query "primaryMasterKey" \
  --output tsv)

echo "✅ Cosmos DB credentials retrieved"

# Step 12: Create App Service Plan
echo ""
echo "📱 Creating App Service Plan (Free tier)..."
APP_SERVICE_PLAN="plan-oss-${TIMESTAMP}"
BACKEND_APP_NAME="backend-oss-${TIMESTAMP}"

az appservice plan create \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_PLAN \
  --location $LOCATION \
  --sku B1 \
  --is-linux

echo "✅ App Service Plan created"

# Step 13: Create Web App
echo ""
echo "🌐 Creating Web App..."
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $BACKEND_APP_NAME \
  --runtime "PYTHON:3.11"

echo "✅ Web App created"

# Step 14: Configure App Settings
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
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
    USE_AZURE_OPENAI="true"

# Set startup command
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $BACKEND_APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"

echo "✅ App settings configured"

# Step 15: Deploy Application Code
echo ""
echo "📦 Preparing deployment package..."

# Create deployment directory
mkdir -p deployment
cd deployment

# Copy Flask app (assuming app.py is in chatbot_backend directory)
if [ -d ../chatbot_backend ]; then
    cp -r ../chatbot_backend/* .
else
    echo "⚠️ chatbot_backend directory not found!"
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
azure-cosmos==4.5.1
EOF

# Create zip package
zip -r ../deployment.zip .
cd ..

echo "🚀 Deploying application..."
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $BACKEND_APP_NAME \
  --src deployment.zip

echo "✅ Backend Application Deployed"

# Step 16.5: Create Admin Flask Server
echo ""
echo "🛠️ Creating Admin Flask Server..."
ADMIN_BACKEND_APP_NAME="admin-backend-oss-${TIMESTAMP}"

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $ADMIN_BACKEND_APP_NAME \
  --runtime "PYTHON:3.11"

echo "✅ Admin Web App created"

# Configure Admin App Settings
echo ""
echo "⚙️ Configuring admin app settings..."
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
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
    USE_AZURE_OPENAI="true"

# Set startup command
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_BACKEND_APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"

echo "✅ Admin app settings configured"

# Deploy Admin Backend Code
echo ""
echo "📦 Preparing admin backend deployment package..."

# Create admin backend deployment directory
mkdir -p admin_backend_deployment
cd admin_backend_deployment

# Copy Admin Flask app
if [ -d ../admin_backend ]; then
    cp -r ../admin_backend/* .
else
    echo "⚠️ admin_backend directory not found!"
fi

# Create requirements.txt for admin backend
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

# Create zip package
zip -r ../admin_backend_deployment.zip .
cd ..

echo "🚀 Deploying admin backend application..."
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_BACKEND_APP_NAME \
  --src admin_backend_deployment.zip

echo "✅ Admin Backend Application Deployed"

# Step 16: Create Frontend Web App
echo ""
echo "🌐 Creating Frontend Web App..."
FRONTEND_APP_NAME="frontend-oss-${TIMESTAMP}"

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $FRONTEND_APP_NAME \
  --runtime "NODE:20-lts"

echo "✅ Frontend Web App created"

# Configure Frontend App Settings
echo ""
echo "⚙️ Configuring frontend app settings..."
FRONTEND_API_URL="https://${FRONTEND_APP_NAME}.azurewebsites.net"

az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $FRONTEND_APP_NAME \
  --settings \
    API_BASE_URL="https://${BACKEND_APP_NAME}.azurewebsites.net" \
    NODE_ENV="production" \
    PORT="5000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

echo "✅ Frontend app settings configured"

# Deploy Frontend Code
echo ""
echo "📦 Preparing frontend deployment package..."

# Create frontend deployment directory
mkdir -p frontend_deployment
cd frontend_deployment

# Copy frontend files
if [ -d ../chatbot_frontend ]; then
    cp -r ../chatbot_frontend/* .
else
    echo "⚠️ chatbot_frontend directory not found!"
fi

# Create zip package
zip -r ../frontend_deployment.zip .
cd ..

echo "🚀 Deploying frontend application..."
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $FRONTEND_APP_NAME \
  --src frontend_deployment.zip

echo "✅ Frontend Application Deployed"

# Step 16.5: Create Admin Dashboard Frontend
echo ""
echo "🎨 Creating Admin Dashboard Frontend..."
ADMIN_FRONTEND_APP_NAME="admin-frontend-oss-${TIMESTAMP}"

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $ADMIN_FRONTEND_APP_NAME \
  --runtime "NODE:20-lts"

echo "✅ Admin Frontend Web App created"

# Configure Admin Frontend App Settings
echo ""
echo "⚙️ Configuring admin frontend app settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_FRONTEND_APP_NAME \
  --settings \
    API_BASE_URL="https://${ADMIN_BACKEND_APP_NAME}.azurewebsites.net" \
    NODE_ENV="production" \
    PORT="5000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

echo "✅ Admin frontend app settings configured"

# Deploy Admin Frontend Code
echo ""
echo "📦 Preparing admin frontend deployment package..."

# Create admin frontend deployment directory
mkdir -p admin_frontend_deployment
cd admin_frontend_deployment

# Copy admin frontend files
if [ -d ../admin_frontend ]; then
    cp -r ../admin_frontend/* .
else
    echo "⚠️ admin_frontend directory not found!"
fi

# Create zip package
zip -r ../admin_frontend_deployment.zip .
cd ..

echo "🚀 Deploying admin frontend application..."
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_FRONTEND_APP_NAME \
  --src admin_frontend_deployment.zip

echo "✅ Admin Frontend Application Deployed"

# Step 17: Create Azure Function App for Analytics
echo ""
echo "⚡ Creating Azure Function App for Analytics..."
FUNCTION_APP_NAME="functions-oss-${TIMESTAMP}"
FUNCTION_STORAGE_NAME="funcstore${TIMESTAMP//-/}"  # Remove hyphens for storage name

# Create storage account for function app
echo "📦 Creating storage account for function app..."
az storage account create \
  --name $FUNCTION_STORAGE_NAME \
  --resource-group $RESOURCE_GROUP \
  --location eastus \
  --sku Standard_LRS

# Create function app
echo "⚡ Creating function app..."
az functionapp create \
  --resource-group $RESOURCE_GROUP \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name $FUNCTION_APP_NAME \
  --storage-account $FUNCTION_STORAGE_NAME \
  --os-type Linux

echo "✅ Function app created"

# Configure Function App Settings
echo ""
echo "⚙️ Configuring function app settings..."
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AZURE_COSMOS_ENDPOINT="${COSMOS_ENDPOINT}" \
    AZURE_COSMOS_KEY="${COSMOS_KEY}" \
    AZURE_COSMOS_DATABASE="voc-analytics"

echo "✅ Function app settings configured"

# Deploy Function Code
echo ""
echo "📦 Preparing function app deployment..."

# Create function deployment directory
mkdir -p function_deployment
cd function_deployment

# Copy function files
if [ -d ../function_app ]; then
    cp -r ../function_app/* .
else
    echo "⚠️ function_app directory not found!"
fi

# Create requirements.txt for function app
cat > requirements.txt << EOF
azure-functions
azure-cosmos
EOF

# Create zip package
zip -r ../function_deployment.zip .
cd ..

echo "🚀 Deploying function app..."
az functionapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --src function_deployment.zip

echo "✅ Analytics Function App Deployed"

# Step 17: Setup Knowledge Base
echo ""
echo "📚 Setting up knowledge base..."

# Create and activate virtual environment
echo "🐍 Setting up Python virtual environment..."
if command -v python3 &> /dev/null; then
    python3.13 -m venv venv
    source venv/bin/activate
    
    # Install required packages for knowledge base setup
    echo "📦 Installing required packages..."
    pip install azure-search-documents python-dotenv langchain-openai
    
    # Create temporary environment file for the setup script
    cat > .env << EOF
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
AZURE_OPENAI_KEY=${AZURE_OPENAI_KEY}
AZURE_OPENAI_MODEL=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Azure AI Search Configuration
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

# Create redeploy script
echo ""
echo "📝 Creating redeploy script..."
cat > redeploy-apps.sh << EOF
#!/bin/bash
set -e

echo "🔄 Redeploying App Services..."

# Hard-coded values from deployment
RESOURCE_GROUP="${RESOURCE_GROUP}"
BACKEND_APP_NAME="${BACKEND_APP_NAME}"
FRONTEND_APP_NAME="${FRONTEND_APP_NAME}"
ADMIN_BACKEND_APP_NAME="${ADMIN_BACKEND_APP_NAME}"
ADMIN_FRONTEND_APP_NAME="${ADMIN_FRONTEND_APP_NAME}"
FUNCTION_APP_NAME="${FUNCTION_APP_NAME}"

echo "Resource Group: \$RESOURCE_GROUP"
echo "Backend App: \$BACKEND_APP_NAME"
echo "Frontend App: \$FRONTEND_APP_NAME"
echo "Admin Backend: \$ADMIN_BACKEND_APP_NAME"
echo "Admin Frontend: \$ADMIN_FRONTEND_APP_NAME"
echo "Function App: \$FUNCTION_APP_NAME"
echo ""

# Function to deploy an app
deploy_app() {
    local app_name=\$1
    local app_type=\$2
    local source_dir=\$3
    
    echo "📦 Redeploying \$app_type: \$app_name..."
    
    # Create deployment directory
    mkdir -p "redeploy_\${app_type}"
    cd "redeploy_\${app_type}"
    
    # Copy source files
    if [ -d "../\$source_dir" ]; then
        cp -r "../\$source_dir"/* .
    else
        echo "⚠️ \$source_dir directory not found!"
        cd ..
        return 1
    fi
    
    # Create requirements.txt for Python apps
    if [[ "\$app_type" == *"backend"* ]]; then
        cat > requirements.txt << 'REQUIREMENTS'
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
REQUIREMENTS
    elif [[ "\$app_type" == "function_app" ]]; then
        cat > requirements.txt << 'REQUIREMENTS'
azure-functions
azure-cosmos
REQUIREMENTS
    fi
    
    # Create zip package
    zip -r "../\${app_type}_redeploy.zip" .
    cd ..
    
    # Deploy
    echo "🚀 Deploying to Azure..."
    if [[ "\$app_type" == "function_app" ]]; then
        az functionapp deployment source config-zip \\
            --resource-group \$RESOURCE_GROUP \\
            --name \$app_name \\
            --src "\${app_type}_redeploy.zip"
    else
        az webapp deployment source config-zip \\
            --resource-group \$RESOURCE_GROUP \\
            --name \$app_name \\
            --src "\${app_type}_redeploy.zip"
    fi
    
    echo "✅ \$app_type redeployed successfully!"
    echo ""
    
    # Cleanup
    rm -rf "redeploy_\${app_type}"
    rm -f "\${app_type}_redeploy.zip"
}

# Ask which apps to redeploy
echo "Select what to redeploy:"
echo "1) Chatbot Backend only"
echo "2) Chatbot Frontend only"
echo "3) Admin Backend only"
echo "4) Admin Frontend only"
echo "5) Analytics Functions only"
echo "6) All Chatbot apps (Backend + Frontend)"
echo "7) All Admin apps (Backend + Frontend)"
echo "8) All Backend services (Chatbot + Admin + Functions)"
echo "9) All apps"
read -p "Enter your choice (1-9): " choice

case \$choice in
    1)
        deploy_app "\$BACKEND_APP_NAME" "chatbot_backend" "chatbot_backend"
        ;;
    2)
        deploy_app "\$FRONTEND_APP_NAME" "chatbot_frontend" "chatbot_frontend"
        ;;
    3)
        deploy_app "\$ADMIN_BACKEND_APP_NAME" "admin_backend" "admin_backend"
        ;;
    4)
        deploy_app "\$ADMIN_FRONTEND_APP_NAME" "admin_frontend" "admin_frontend"
        ;;
    5)
        deploy_app "\$FUNCTION_APP_NAME" "function_app" "function_app"
        ;;
    6)
        deploy_app "\$BACKEND_APP_NAME" "chatbot_backend" "chatbot_backend"
        deploy_app "\$FRONTEND_APP_NAME" "chatbot_frontend" "chatbot_frontend"
        ;;
    7)
        deploy_app "\$ADMIN_BACKEND_APP_NAME" "admin_backend" "admin_backend"
        deploy_app "\$ADMIN_FRONTEND_APP_NAME" "admin_frontend" "admin_frontend"
        ;;
    8)
        deploy_app "\$BACKEND_APP_NAME" "chatbot_backend" "chatbot_backend"
        deploy_app "\$ADMIN_BACKEND_APP_NAME" "admin_backend" "admin_backend"
        deploy_app "\$FUNCTION_APP_NAME" "function_app" "function_app"
        ;;
    9)
        deploy_app "\$BACKEND_APP_NAME" "chatbot_backend" "chatbot_backend"
        deploy_app "\$FRONTEND_APP_NAME" "chatbot_frontend" "chatbot_frontend"
        deploy_app "\$ADMIN_BACKEND_APP_NAME" "admin_backend" "admin_backend"
        deploy_app "\$ADMIN_FRONTEND_APP_NAME" "admin_frontend" "admin_frontend"
        deploy_app "\$FUNCTION_APP_NAME" "function_app" "function_app"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo "🎉 Redeployment complete!"
echo ""
echo "💡 Tips:"
echo "- Check app logs: az webapp log tail --name <app-name> --resource-group \$RESOURCE_GROUP"
echo "- Check function logs: az functionapp logs --name <function-name> --resource-group \$RESOURCE_GROUP"
echo "- Restart app: az webapp restart --name <app-name> --resource-group \$RESOURCE_GROUP"
echo "- Restart function: az functionapp restart --name <function-name> --resource-group \$RESOURCE_GROUP"

EOF

chmod +x redeploy-apps.sh
echo "✅ Created redeploy-apps.sh"

# Step 18: Final Summary
BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"
FRONTEND_URL="https://${FRONTEND_APP_NAME}.azurewebsites.net"
ADMIN_BACKEND_URL="https://${ADMIN_BACKEND_APP_NAME}.azurewebsites.net"
ADMIN_FRONTEND_URL="https://${ADMIN_FRONTEND_APP_NAME}.azurewebsites.net"

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
echo "Azure Cosmos DB:"
echo "  Account: $COSMOS_ACCOUNT_NAME"
echo "  Endpoint: $COSMOS_ENDPOINT"
echo "  Database: voc-analytics"
echo "  Container: conversations"
echo ""
echo "Chatbot Services:"
echo "  Backend: $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
echo ""
echo "Admin Services:"
echo "  Backend: $ADMIN_BACKEND_URL"
echo "  Frontend: $ADMIN_FRONTEND_URL"
echo ""

# Save deployment info
cat > deployment-info.json << EOF
{
  "resource_group": "${RESOURCE_GROUP}",
  "frontend_app_url": "${FRONTEND_URL}",
  "backend_app_url": "${BACKEND_URL}",
  "admin_frontend_url": "${ADMIN_FRONTEND_URL}",
  "admin_backend_url": "${ADMIN_BACKEND_URL}",
  "azure_openai_endpoint": "${AZURE_OPENAI_ENDPOINT}",
  "search_endpoint": "${SEARCH_ENDPOINT}",
  "search_index": "oss-knowledge-base",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "📄 Deployment info saved to deployment-info.json"

echo ""
echo "🤖 Your OSS chatbot is ready!"
echo "Frontend: ${FRONTEND_URL}"
echo "Backend API: ${BACKEND_URL}"