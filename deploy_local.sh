#!/bin/bash
set -e

echo "🚀 Starting local development Azure OpenAI deployment..."

# Configuration
RESOURCE_GROUP="rg-oss-chatbot-local"
LOCATION="canadaeast"
TIMESTAMP=$(date +%m%d-%H%M)
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

# Step 11: Create .env file for local development
echo ""
echo "📝 Creating .env file for local development..."
cat > .env << EOF
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
AZURE_OPENAI_KEY=${AZURE_OPENAI_KEY}
AZURE_OPENAI_MODEL=gpt-4o-mini

# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT=${SEARCH_ENDPOINT}
AZURE_SEARCH_KEY=${SEARCH_KEY}
AZURE_SEARCH_INDEX=oss-knowledge-base

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

# Save deployment info for cleanup
cat > local-deployment-info.json << EOF
{
  "resource_group": "${RESOURCE_GROUP}",
  "openai_service": "${OPENAI_SERVICE_NAME}",
  "search_service": "${SEARCH_SERVICE_NAME}",
  "azure_openai_endpoint": "${AZURE_OPENAI_ENDPOINT}",
  "search_endpoint": "${SEARCH_ENDPOINT}",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "📄 Deployment info saved to local-deployment-info.json"

echo ""
echo "🚀 Next Steps:"
echo "1. Run the chatbot locally:"
echo "   ./run-local.sh"
echo ""
echo "2. Test the chat endpoint:"
echo "   ./test-chat.sh \"Hello, I need help\""
echo ""
echo "3. Make changes to app.py and restart with:"
echo "   Ctrl+C (to stop) then ./run-local.sh (to restart)"
echo ""
echo "4. When done developing, clean up Azure resources:"
echo "   ./cleanup-local.sh"
echo ""
echo "💡 Your .env file contains all the Azure credentials"
echo "🔒 Keep your .env file secure and don't commit it to git!"