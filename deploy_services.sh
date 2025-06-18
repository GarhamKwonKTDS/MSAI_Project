#!/bin/bash
set -e

echo "🚀 Starting Azure Services deployment (Part 1)..."

# Configuration
LOCATION="${LOCATION:-australiaeast}"
TIMESTAMP=$(date +%m%d-%H%M)
RESOURCE_GROUP="rg-oss-chatbot-dev-${TIMESTAMP}"

echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
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
OPENAI_SERVICE_NAME="openai-oss-${TIMESTAMP}"

az cognitiveservices account create \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_SERVICE_NAME \
  --location $LOCATION \
  --kind OpenAI \
  --sku S0 \
  --yes

echo "✅ OpenAI service created"
echo ""

# Step 3: Wait and deploy models
echo "⏳ Waiting 20 seconds for service to be ready..."
sleep 20

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

echo "✅ Model deployment complete!"

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

# Get OpenAI credentials
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

echo "✅ OpenAI credentials retrieved"

# Step 4: Create Azure AI Search
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

# Wait for Search
echo "⏳ Waiting for Search service to be ready..."
sleep 30

# Get Search credentials
echo "🔑 Getting Search credentials..."
SEARCH_KEY=$(az search admin-key show \
  --resource-group $RESOURCE_GROUP \
  --service-name $SEARCH_SERVICE_NAME \
  --query "primaryKey" \
  --output tsv)

SEARCH_ENDPOINT="https://${SEARCH_SERVICE_NAME}.search.windows.net"

echo "✅ Search credentials retrieved"

# Step 5: Create Cosmos DB
echo ""
echo "🌍 Creating Cosmos DB account..."
COSMOS_ACCOUNT_NAME="cosmos-oss-${TIMESTAMP}"
COSMOS_LOCATION="${COSMOS_LOCATION:-westus3}"
echo "⚠️ Using $COSMOS_LOCATION for Cosmos DB due to capacity constraints"

az cosmosdb create \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT_NAME \
  --locations regionName=$COSMOS_LOCATION failoverPriority=0 isZoneRedundant=false \
  --default-consistency-level "Session"

echo "✅ Cosmos DB account created"

# Wait for Cosmos DB
echo "⏳ Waiting for Cosmos DB to be ready..."
sleep 30

# Create database and containers
echo "📦 Creating Cosmos DB database and containers..."
az cosmosdb sql database create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --name "voc-analytics"

# Create containers
for container in "turns" "conversations" "statistics"; do
  echo "  Creating container: $container"
  az cosmosdb sql container create \
    --resource-group $RESOURCE_GROUP \
    --account-name $COSMOS_ACCOUNT_NAME \
    --database-name "voc-analytics" \
    --name $container \
    --partition-key-path "/session_id" \
    --throughput 400
done

echo "✅ Cosmos DB setup complete"

# Get Cosmos DB credentials
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

# Step 6: Save service configuration
echo ""
echo "💾 Saving service configuration..."

# Create services-config.json
cat > services-config.json << EOF
{
  "resource_group": "${RESOURCE_GROUP}",
  "location": "${LOCATION}",
  "timestamp": "${TIMESTAMP}",
  "openai": {
    "service_name": "${OPENAI_SERVICE_NAME}",
    "endpoint": "${AZURE_OPENAI_ENDPOINT}",
    "key": "${AZURE_OPENAI_KEY}",
    "model": "gpt-4o-mini",
    "embedding_model": "text-embedding-3-small"
  },
  "search": {
    "service_name": "${SEARCH_SERVICE_NAME}",
    "endpoint": "${SEARCH_ENDPOINT}",
    "key": "${SEARCH_KEY}",
    "index": "oss-knowledge-base"
  },
  "cosmos": {
    "account_name": "${COSMOS_ACCOUNT_NAME}",
    "endpoint": "${COSMOS_ENDPOINT}",
    "key": "${COSMOS_KEY}",
    "database": "voc-analytics",
    "containers": ["turns", "conversations", "statistics"]
  },
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "✅ Configuration saved to services-config.json"

# Create .env file for knowledge base setup
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

echo "✅ Environment file created"

# Step 7: Setup Knowledge Base
echo ""
echo "📚 Setting up knowledge base..."

if command -v python3 &> /dev/null; then
    echo "🐍 Setting up Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    
    echo "📦 Installing required packages..."
    pip install azure-search-documents python-dotenv langchain-openai
    
    if [ -f setup_search_index.py ]; then
        echo "🚀 Running knowledge base setup..."
        python setup_search_index.py
        echo "✅ Knowledge base setup complete"
    else
        echo "⚠️ setup_search_index.py not found! Please run it manually later."
    fi
    
    deactivate
    rm -rf venv
else
    echo "⚠️ Python3 not found. Please run setup_search_index.py manually."
fi

# Summary
echo ""
echo "🎉 Azure Services deployment completed!"
echo "================================"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo ""
echo "✅ Azure OpenAI Service deployed"
echo "✅ Azure AI Search deployed"
echo "✅ Azure Cosmos DB deployed"
echo "✅ Knowledge base configured"
echo ""
echo "📄 Configuration saved to: services-config.json"
echo "🔐 Environment variables saved to: .env"
echo ""
echo "🚀 Next steps:"
echo "1. Run ./deploy_apps.sh to deploy applications"
echo "2. Or run ./deploy_apps.sh <path-to-config> to use different config"
echo ""
echo "💡 To clean up services later:"
echo "   az group delete --name $RESOURCE_GROUP --yes"