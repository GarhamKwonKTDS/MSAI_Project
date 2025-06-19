#!/bin/bash
set -e

echo "🚀 Starting local development setup..."

# Check if services config exists
CONFIG_FILE="${1:-services-config.json}"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    echo "Please run ./deploy_services.sh first or provide path to config file"
    exit 1
fi

echo "📋 Loading Azure services configuration from: $CONFIG_FILE"

# Extract configuration using Python (more reliable than jq)
read_config() {
    python3 -c "import json; data=json.load(open('$CONFIG_FILE')); print(data$1)"
}

# Load configuration
RESOURCE_GROUP=$(read_config "['resource_group']")
TIMESTAMP=$(read_config "['timestamp']")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=$(read_config "['openai']['endpoint']")
AZURE_OPENAI_KEY=$(read_config "['openai']['key']")
OPENAI_MODEL=$(read_config "['openai']['model']")
EMBEDDING_MODEL=$(read_config "['openai']['embedding_model']")

# Azure Search
SEARCH_ENDPOINT=$(read_config "['search']['endpoint']")
SEARCH_KEY=$(read_config "['search']['key']")
SEARCH_INDEX=$(read_config "['search']['index']")

# Azure Cosmos DB
COSMOS_ENDPOINT=$(read_config "['cosmos']['endpoint']")
COSMOS_KEY=$(read_config "['cosmos']['key']")
COSMOS_DATABASE=$(read_config "['cosmos']['database']")

echo "✅ Configuration loaded successfully"
echo "  Using Resource Group: $RESOURCE_GROUP"
echo ""

# Step 1: Create .env file for local development
echo "📝 Creating .env file for local development..."
cat > .env << EOF
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
AZURE_OPENAI_KEY=${AZURE_OPENAI_KEY}
AZURE_OPENAI_MODEL=${OPENAI_MODEL}
AZURE_OPENAI_EMBEDDING_MODEL=${EMBEDDING_MODEL}

# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT=${SEARCH_ENDPOINT}
AZURE_SEARCH_KEY=${SEARCH_KEY}
AZURE_SEARCH_INDEX=${SEARCH_INDEX}

# Azure Cosmos DB Configuration
AZURE_COSMOS_ENDPOINT=${COSMOS_ENDPOINT}
AZURE_COSMOS_KEY=${COSMOS_KEY}
AZURE_COSMOS_DATABASE=${COSMOS_DATABASE}
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

# Step 2: Create Python virtual environment
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

# Step 3: Create run script for easy development
echo ""
echo "🛠️ Creating development scripts..."

# Create run-local.sh script
cat > run-local.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting OSS Chatbot (Backend + Frontend)..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found! Run ./deploy_local.sh first"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Run ./deploy_local.sh first"
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

# Create run-admin.sh script (if admin directories exist)
if [ -d "admin_backend" ] && [ -d "admin_frontend" ]; then
cat > run-admin.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting OSS Admin Services (Backend + Frontend)..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found! Run ./deploy_local.sh first"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Run ./deploy_local.sh first"
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
fi

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

# Step 4: Final Summary
echo ""
echo "🎉 Local development environment setup completed!"
echo "================================================="
echo "Connected to Azure services in resource group: $RESOURCE_GROUP"
echo ""
echo "Azure Services Being Used:"
echo "  🤖 Azure OpenAI: ${AZURE_OPENAI_ENDPOINT}"
echo "  🔍 Azure Search: ${SEARCH_ENDPOINT}"
echo "  🌍 Azure Cosmos DB: ${COSMOS_ENDPOINT}"
echo ""

# Save local development info
cat > local-dev-info.json << EOF
{
  "setup_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "using_services_from": "${CONFIG_FILE}",
  "resource_group": "${RESOURCE_GROUP}",
  "local_ports": {
    "chatbot_backend": 8080,
    "chatbot_frontend": 8081,
    "admin_backend": 8082,
    "admin_frontend": 8083
  }
}
EOF

echo "📄 Local development info saved to local-dev-info.json"

echo ""
echo "🚀 Next Steps:"
echo "1. Run the chatbot locally:"
echo "   ./run-local.sh"
echo ""
if [ -d "admin_backend" ] && [ -d "admin_frontend" ]; then
echo "2. Run the admin services:"
echo "   ./run-admin.sh"
echo ""
fi
echo "3. Test the services:"
echo "   ./test-chat.sh \"Hello, I need help\""
echo ""
echo "4. Access the services:"
echo "   Chatbot Frontend: http://localhost:8081"
echo "   Chatbot Backend: http://localhost:8080"
if [ -d "admin_backend" ] && [ -d "admin_frontend" ]; then
echo "   Admin Frontend: http://localhost:8083"
echo "   Admin Backend: http://localhost:8082"
fi
echo ""
echo "5. Make changes and restart with:"
echo "   Ctrl+C (to stop) then ./run-local.sh (to restart)"
echo ""
echo "💡 Your .env file contains all Azure service credentials"
echo "🔒 Keep your credential files secure and don't commit them to git!"
echo ""
echo "📝 Note: This setup uses Azure services from resource group: $RESOURCE_GROUP"
echo "   To use different services, run: ./deploy_local.sh <path-to-services-config.json>"