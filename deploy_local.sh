#!/bin/bash
set -e

echo "🚀 Starting local development Azure OpenAI deployment..."

# Configuration (default: canadaeast)
LOCATION="australiaeast"
TIMESTAMP=$(date +%m%d-%H%M)
RESOURCE_GROUP="rg-oss-chatbot-local-${TIMESTAMP}"
OPENAI_SERVICE_NAME="openai-local-${TIMESTAMP}"

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
echo "🎉 Model deployed successfully!"

# Step 7: Get OpenAI credentials
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
SEARCH_SERVICE_NAME="search-local-${TIMESTAMP}"

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

# Step 10a: Create Cosmos DB Account
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

# Step 11: Create .env file for local development
echo ""
echo "📝 Creating .env file for local development..."
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

# Azure Cosmos DB Configuration
AZURE_COSMOS_ENDPOINT=${COSMOS_ENDPOINT}
AZURE_COSMOS_KEY=${COSMOS_KEY}
AZURE_COSMOS_DATABASE=voc-analytics
AZURE_COSMOS_TURNS_CONTAINER=turns
AZURE_COSMOS_CONVERSATIONS_CONTAINER=conversations
AZURE_COSMOS_STATISTICS_CONTAINER=statistics

# Local Development Settings
FLASK_ENV=development
FLASK_DEBUG=true
PORT=8080
RAG_ENABLED=true
RAG_TOP_K=3
EOF

echo "✅ .env file created"

# Step 12: Create Python virtual environment
echo ""
echo "🐍 Setting up Python virtual environment..."
if command -v python3 &> /dev/null; then
    python3 -m venv venv
    source venv/bin/activate

    echo "📄 Creating requirements.txt..."
    cat > chatbot_backend/requirements.txt << EOF
flask==3.0.0
flask-cors==4.0.0
langchain>=0.1.17
langchain-openai>=0.1.6
langgraph>=0.0.37
azure-search-documents==11.4.0
azure-core==1.29.5
python-dotenv==1.0.0
openai>=1.55.3
httpx>=0.28
pydantic>=2.0.0
azure-cosmos==4.5.1
EOF
    
    # Install required packages
    echo "📦 Installing required packages..."
    pip install --upgrade pip
    pip install -r chatbot_backend/requirements.txt
    
    echo "✅ Virtual environment and packages installed"
    deactivate
else
    echo "⚠️ Python3 not found. Please install Python 3 to set up the virtual environment."
fi

# Step 13: Setup Knowledge Base (if setup script exists)
echo ""
echo "📚 Setting up knowledge base..."
if [ -f setup_search_index.py ]; then
    source venv/bin/activate
    echo "🚀 Running knowledge base setup..."
    python setup_search_index.py
    deactivate
    echo "✅ Knowledge base setup complete"
else
    echo "⚠️ setup_search_index.py not found - skipping knowledge base setup"
fi

# Step 14: Create run script for easy development
echo ""
echo "🛠️ Creating development scripts..."

# Create run-local.sh script
cat > run-local.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting OSS Chatbot (Backend + Frontend)..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found! Run ./deploy-local.sh first"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Run ./deploy-local.sh first"
    exit 1
fi

# Check if frontend directory exists
if [ ! -d "chatbot_frontend" ]; then
    echo "❌ chatbot_frontend directory not found!"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found! Please install Node.js to run the frontend."
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "✅ Servers stopped"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Start Backend
echo "🐍 Starting Flask backend..."
source venv/bin/activate

export FLASK_ENV=development
export FLASK_DEBUG=true
export PORT=8080

cd chatbot_backend
python app.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start Frontend
echo "🌐 Starting Node.js frontend..."

export API_BASE_URL=http://localhost:8080
export PORT=8081
export NODE_ENV=development

cd chatbot_frontend
node server.js &
FRONTEND_PID=$!
cd ..

# Display status
echo ""
echo "🎉 Both servers started successfully!"
echo "================================="
echo "📱 Frontend: http://localhost:8081"
echo "🔗 Backend API: http://localhost:8080"
echo "🏥 Health Check: http://localhost:8080/health"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
EOF

chmod +x run-local.sh

# Create run-admin.sh script
cat > run-admin.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting OSS Admin Services (Backend + Frontend)..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found! Run ./deploy-local.sh first"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Run ./deploy-local.sh first"
    exit 1
fi

# Check if admin directories exist
if [ ! -d "admin_backend" ]; then
    echo "❌ admin_backend directory not found!"
    exit 1
fi

if [ ! -d "admin_frontend" ]; then
    echo "❌ admin_frontend directory not found!"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found! Please install Node.js to run the frontend."
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down admin servers..."
    if [ ! -z "$ADMIN_BACKEND_PID" ]; then
        kill $ADMIN_BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$ADMIN_FRONTEND_PID" ]; then
        kill $ADMIN_FRONTEND_PID 2>/dev/null || true
    fi
    echo "✅ Admin servers stopped"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Start Admin Backend
echo "🐍 Starting Flask admin backend..."
source venv/bin/activate

export FLASK_ENV=development
export FLASK_DEBUG=true
export PORT=8082

cd admin_backend
python app.py &
ADMIN_BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start Admin Frontend
echo "🌐 Starting Node.js admin frontend..."

export API_BASE_URL=http://localhost:8082
export PORT=8083
export NODE_ENV=development

cd admin_frontend
node server.js &
ADMIN_FRONTEND_PID=$!
cd ..

# Display status
echo ""
echo "🎉 Admin services started successfully!"
echo "================================="
echo "📱 Admin Frontend: http://localhost:8083"
echo "🔗 Admin Backend API: http://localhost:8082"
echo "🏥 Health Check: http://localhost:8082/health"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for either process to exit
wait $ADMIN_BACKEND_PID $ADMIN_FRONTEND_PID
EOF

chmod +x run-admin.sh

# Create test script
cat > test-chat.sh << 'EOF'
#!/bin/bash
echo "🧪 Testing chat endpoint..."

if [ $# -eq 0 ]; then
    MESSAGE="Hello, I need help with OSS login issues"
else
    MESSAGE="$1"
fi

echo "Sending message: $MESSAGE"
echo ""

curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"$MESSAGE\",\"session_id\":\"test-session\"}" \
  | python -m json.tool

echo ""
echo "Usage: ./test-chat.sh \"Your message here\""
EOF

chmod +x test-chat.sh

# Step 15: Final Summary
echo ""
echo "🎉 Local development environment setup completed!"
echo "================================================="
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

# Save deployment info for cleanup
cat > local-deployment-info.json << EOF
{
  "resource_group": "${RESOURCE_GROUP}",
  "openai_service": "${OPENAI_SERVICE_NAME}",
  "search_service": "${SEARCH_SERVICE_NAME}",
  "cosmos_account": "${COSMOS_ACCOUNT_NAME}",
  "azure_openai_endpoint": "${AZURE_OPENAI_ENDPOINT}",
  "search_endpoint": "${SEARCH_ENDPOINT}",
  "cosmos_endpoint": "${COSMOS_ENDPOINT}",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "📄 Deployment info saved to local-deployment-info.json"

echo ""
echo "🚀 Next Steps:"
echo "1. Run the chatbot locally:"
echo "   ./run-local.sh"
echo ""
echo "2. Run the admin services:"
echo "   ./run-admin.sh"
echo ""
echo "3. Run Azure Functions locally:"
echo "   ./run-functions.sh"
echo ""
echo "4. Test the services:"
echo "   ./test-chat.sh \"Hello, I need help\""
echo "   ./test-analytics.sh"
echo "   ./test-batch-processing.sh"
echo ""
echo "5. Access the services:"
echo "   Chatbot Frontend: http://localhost:8081"
echo "   Chatbot Backend: http://localhost:8080"
echo "   Admin Frontend: http://localhost:8083"
echo "   Admin Backend: http://localhost:8082"
echo "   Azure Functions: http://localhost:7071"
echo ""
echo "6. Function Endpoints (when running locally):"
echo "   Analytics API: http://localhost:7071/api/analytics"
echo "   Process Conversations: http://localhost:7071/api/process-conversations"
echo ""
echo "7. Make changes and restart with:"
echo "   Ctrl+C (to stop) then ./run-[service].sh (to restart)"
echo ""
echo "8. When done developing, clean up Azure resources:"
echo "   ./cleanup.sh"
echo ""
echo "💡 Your .env and local.settings.json files contain all credentials"
echo "🔒 Keep your credential files secure and don't commit them to git!"