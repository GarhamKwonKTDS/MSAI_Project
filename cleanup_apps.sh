#!/bin/bash
set -e

echo "🧹 Starting Apps cleanup..."

# Check for apps config file
CONFIG_FILE="${1:-apps-config.json}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Apps configuration file not found: $CONFIG_FILE"
    echo "Please provide the apps-config.json file from deployment"
    exit 1
fi

echo "📄 Loading configuration from: $CONFIG_FILE"

# Load configuration
if command -v jq &> /dev/null; then
    # Use jq if available
    RESOURCE_GROUP=$(jq -r '.resource_group' "$CONFIG_FILE")
    APP_SERVICE_PLAN=$(jq -r '.app_service_plan' "$CONFIG_FILE")
    
    # App names
    BACKEND_APP_NAME=$(jq -r '.chatbot.backend.name' "$CONFIG_FILE")
    FRONTEND_APP_NAME=$(jq -r '.chatbot.frontend.name' "$CONFIG_FILE")
    ADMIN_BACKEND_APP_NAME=$(jq -r '.admin.backend.name' "$CONFIG_FILE")
    ADMIN_FRONTEND_APP_NAME=$(jq -r '.admin.frontend.name' "$CONFIG_FILE")
    FUNCTION_APP_NAME=$(jq -r '.function.name' "$CONFIG_FILE")
    FUNCTION_STORAGE_NAME=$(jq -r '.function.storage' "$CONFIG_FILE")
else
    # Fallback to python
    echo "Using Python to parse config..."
    RESOURCE_GROUP=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['resource_group'])")
    APP_SERVICE_PLAN=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['app_service_plan'])")
    
    BACKEND_APP_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['chatbot']['backend']['name'])")
    FRONTEND_APP_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['chatbot']['frontend']['name'])")
    ADMIN_BACKEND_APP_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['admin']['backend']['name'])")
    ADMIN_FRONTEND_APP_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['admin']['frontend']['name'])")
    FUNCTION_APP_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['function']['name'])")
    FUNCTION_STORAGE_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['function']['storage'])")
fi

echo "✅ Configuration loaded"
echo ""
echo "🎯 Apps to be deleted:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  - Chatbot Backend: $BACKEND_APP_NAME"
echo "  - Chatbot Frontend: $FRONTEND_APP_NAME"
echo "  - Admin Backend: $ADMIN_BACKEND_APP_NAME"
echo "  - Admin Frontend: $ADMIN_FRONTEND_APP_NAME"
echo "  - Function App: $FUNCTION_APP_NAME"
echo "  - Function Storage: $FUNCTION_STORAGE_NAME"
echo "  - App Service Plan: $APP_SERVICE_PLAN"
echo ""

# Confirm deletion
echo "⚠️ This will delete all the applications but keep Azure services (OpenAI, Search, Cosmos)"
read -p "Continue with apps cleanup? (y/n): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

# Start deletion
echo ""
echo "🗑️ Deleting applications..."

# Delete Web Apps
for app in "$BACKEND_APP_NAME" "$FRONTEND_APP_NAME" "$ADMIN_BACKEND_APP_NAME" "$ADMIN_FRONTEND_APP_NAME"; do
    echo "  Deleting web app: $app"
    az webapp delete \
        --name $app \
        --resource-group $RESOURCE_GROUP \
        --keep-empty-plan || echo "    ⚠️ Failed to delete $app (may not exist)"
done

# Delete Function App
echo "  Deleting function app: $FUNCTION_APP_NAME"
az functionapp delete \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP || echo "    ⚠️ Failed to delete $FUNCTION_APP_NAME (may not exist)"

# Delete Function Storage Account
echo "  Deleting storage account: $FUNCTION_STORAGE_NAME"
az storage account delete \
    --name $FUNCTION_STORAGE_NAME \
    --resource-group $RESOURCE_GROUP \
    --yes || echo "    ⚠️ Failed to delete $FUNCTION_STORAGE_NAME (may not exist)"

# Delete App Service Plan
echo "  Deleting app service plan: $APP_SERVICE_PLAN"
az appservice plan delete \
    --name $APP_SERVICE_PLAN \
    --resource-group $RESOURCE_GROUP \
    --yes || echo "    ⚠️ Failed to delete $APP_SERVICE_PLAN (may not exist)"

echo ""
echo "✅ Apps cleanup completed!"
echo ""
echo "📌 Remaining Azure services:"
echo "  - Azure OpenAI"
echo "  - Azure AI Search" 
echo "  - Azure Cosmos DB"
echo ""
echo "These services are still running and incurring costs."
echo ""
echo "🚀 To redeploy apps:"
echo "   ./deploy_apps.sh services-config.json"
echo ""
echo "🗑️ To delete all services and clean up completely:"
echo "   az group delete --name $RESOURCE_GROUP --yes"

# Archive the apps config
if [ -f "$CONFIG_FILE" ]; then
    ARCHIVE_NAME="apps-config-deleted-$(date +%Y%m%d-%H%M%S).json"
    mv "$CONFIG_FILE" "$ARCHIVE_NAME"
    echo ""
    echo "📁 Apps config archived to: $ARCHIVE_NAME"
fi