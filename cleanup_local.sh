#!/bin/bash

echo "🧹 Starting local development cleanup..."

# Configuration
RESOURCE_GROUP="rg-oss-chatbot-local"

# ================================
# Check if resource group exists
# ================================

if az group show --name $RESOURCE_GROUP &> /dev/null; then
    echo "📁 Found resource group: $RESOURCE_GROUP"
    
    # List resources that will be deleted
    echo "📋 Resources to be deleted:"
    az resource list --resource-group $RESOURCE_GROUP --output table
    
    # Confirm deletion
    echo ""
    echo "⚠️ This will delete ALL Azure resources in the resource group!"
    echo "💰 This will stop all Azure costs for your local development"
    read -p "Continue with cleanup? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️ Deleting resource group and all resources..."
        az group delete --name $RESOURCE_GROUP --yes --no-wait
        
        echo "✅ Azure resource cleanup initiated successfully!"
        echo "Resources will be deleted in the background (usually takes 2-5 minutes)"
        echo "💰 All Azure costs will stop accruing once deletion is complete"
    else
        echo "❌ Azure cleanup cancelled"
        echo "💡 You can run this script again later to clean up Azure resources"
    fi
else
    echo "ℹ️ Azure resource group $RESOURCE_GROUP not found - no Azure resources to clean up"
fi

# ================================
# Clean up local development files
# ================================

echo ""
echo "🧹 Cleaning up local development files..."

# Ask about local files cleanup
echo "🗂️ Local development files found:"
ls -la | grep -E "(\.env|venv|.*local.*|.*\.log)" || echo "  (no local dev files found)"

echo ""
echo "Would you like to clean up local development files?"
echo "  - .env file (contains your Azure credentials)"
echo "  - venv/ directory (Python virtual environment)"
echo "  - local development scripts"
echo "  - deployment info files"
read -p "Clean up local files? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    
    # Remove .env file
    if [ -f ".env" ]; then
        rm .env
        echo "  ✅ Removed .env file"
    fi
    
    # Remove virtual environment
    if [ -d "venv" ]; then
        rm -rf venv
        echo "  ✅ Removed Python virtual environment"
    fi
    
    # Remove development scripts
    if [ -f "run-local.sh" ]; then
        rm run-local.sh
        echo "  ✅ Removed run-local.sh"
    fi
    
    if [ -f "test-chat.sh" ]; then
        rm test-chat.sh
        echo "  ✅ Removed test-chat.sh"
    fi
    
    # Remove deployment info
    if [ -f "local-deployment-info.json" ]; then
        rm local-deployment-info.json
        echo "  ✅ Removed local-deployment-info.json"
    fi
    
    # Remove any log files
    if ls *.log 1> /dev/null 2>&1; then
        rm *.log
        echo "  ✅ Removed log files"
    fi
    
    # Remove any temporary files
    if [ -d "__pycache__" ]; then
        rm -rf __pycache__
        echo "  ✅ Removed Python cache"
    fi
    
    echo "✅ Local development files cleaned up"
    
else
    echo "⏭️ Keeping local development files"
    echo "💡 You can manually delete them later if needed:"
    echo "   - .env (contains Azure credentials)"
    echo "   - venv/ (Python virtual environment)"
    echo "   - run-local.sh, test-chat.sh (development scripts)"
fi

# ================================
# Check for running processes
# ================================

echo ""
echo "🔍 Checking for running Flask processes..."

FLASK_PIDS=$(pgrep -f "python.*app.py" || true)
if [ -n "$FLASK_PIDS" ]; then
    echo "⚠️ Found running Flask processes:"
    ps aux | grep "python.*app.py" | grep -v grep
    echo ""
    read -p "Kill running Flask processes? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$FLASK_PIDS" | xargs kill -9 2>/dev/null || true
        echo "✅ Stopped running Flask processes"
    fi
else
    echo "✅ No running Flask processes found"
fi

# ================================
# Summary
# ================================

echo ""
echo "🎉 Local development cleanup completed!"
echo "======================================="

if az group show --name $RESOURCE_GROUP &> /dev/null 2>&1; then
    echo "⏳ Azure resources deletion in progress"
    echo "💰 Costs will stop once deletion completes (~2-5 minutes)"
else
    echo "✅ Azure resources cleaned up"
    echo "💰 No Azure costs being incurred"
fi

echo "✅ Local development environment cleaned"
echo ""
echo "🚀 To set up local development again:"
echo "   ./deploy-local.sh"
echo ""
echo "💡 Tips:"
echo "   - Keep app.py and other source files (they weren't deleted)" 
echo "   - Your Azure subscription is clean and ready for new deployments"
echo "   - Run 'az account show' to verify your Azure connection"