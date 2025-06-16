#!/bin/bash

echo "🧹 Starting cleanup..."

# ================================
# Detect which resource groups exist
# ================================

PROD_RESOURCE_GROUP="rg-oss-chatbot-dev"
LOCAL_RESOURCE_GROUP="rg-oss-chatbot-local"
FOUND_GROUPS=()

echo "🔍 Checking for Azure resource groups..."

if az group show --name $PROD_RESOURCE_GROUP &> /dev/null; then
    echo "  ✓ Found production: $PROD_RESOURCE_GROUP"
    FOUND_GROUPS+=("$PROD_RESOURCE_GROUP")
fi

if az group show --name $LOCAL_RESOURCE_GROUP &> /dev/null; then
    echo "  ✓ Found local: $LOCAL_RESOURCE_GROUP"
    FOUND_GROUPS+=("$LOCAL_RESOURCE_GROUP")
fi

# ================================
# Handle Azure resource cleanup
# ================================

if [ ${#FOUND_GROUPS[@]} -eq 0 ]; then
    echo "ℹ️ No Azure resource groups found"
else
    echo ""
    echo "📋 Found ${#FOUND_GROUPS[@]} resource group(s) to clean up"
    
    for RG in "${FOUND_GROUPS[@]}"; do
        echo ""
        echo "🔹 Resource Group: $RG"
        echo "   Resources:"
        az resource list --resource-group $RG --output table
    done
    
    echo ""
    echo "⚠️ This will delete ALL resources in the above resource group(s)!"
    echo "💰 This will stop all Azure costs for these resources"
    read -p "Continue with Azure cleanup? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for RG in "${FOUND_GROUPS[@]}"; do
            echo "🗑️ Deleting resource group: $RG..."
            az group delete --name $RG --yes --no-wait
        done
        echo "✅ Azure resource cleanup initiated!"
        echo "Resources will be deleted in the background (2-5 minutes)"
    else
        echo "⏭️ Skipping Azure cleanup"
    fi
fi

# ================================
# Clean up local files
# ================================

echo ""
echo "🧹 Cleaning up local files..."
echo ""
echo "The following will be removed:"
echo "  - Deployment directories (deployment/, frontend_deployment/)"
echo "  - Deployment packages (*.zip)"
echo "  - Environment files (.env, search-config.env)"
echo "  - Virtual environment (venv/)"
echo "  - Log files (*.log)"
echo "  - Python cache (__pycache__)"
echo "  - Deployment info files (*deployment-info.json)"
echo "  - Development scripts (run-local.sh, test-chat.sh)"
echo ""
read -p "Clean up local files? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    
    # Remove deployment directories
    if [ -d "deployment" ]; then
        rm -rf deployment
        echo "  ✅ Removed deployment/"
    fi
    
    if [ -d "frontend_deployment" ]; then
        rm -rf frontend_deployment
        echo "  ✅ Removed frontend_deployment/"
    fi
    
    # Remove zip files
    if ls *.zip 1> /dev/null 2>&1; then
        rm *.zip
        echo "  ✅ Removed deployment zip files"
    fi
    
    # Remove environment files
    if [ -f ".env" ]; then
        rm .env
        echo "  ✅ Removed .env"
    fi
    
    if [ -f "search-config.env" ]; then
        rm search-config.env
        echo "  ✅ Removed search-config.env"
    fi
    
    # Remove virtual environment
    if [ -d "venv" ]; then
        rm -rf venv
        echo "  ✅ Removed Python virtual environment"
    fi
    
    # Remove log files
    if ls *.log 1> /dev/null 2>&1; then
        rm *.log
        echo "  ✅ Removed log files"
    fi
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo "  ✅ Removed Python cache directories"
    
    # Remove deployment info files
    if ls *deployment-info.json 1> /dev/null 2>&1; then
        rm *deployment-info.json
        echo "  ✅ Removed deployment info files"
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
    
    echo ""
    echo "✅ Local files cleaned up"
    
else
    echo "⏭️ Keeping local files"
fi

# ================================
# Check for running processes
# ================================

echo ""
echo "🔍 Checking for running processes..."

FLASK_PIDS=$(pgrep -f "python.*chatbot_backend/app.py" || true)
NODE_PIDS=$(pgrep -f "node.*chatbot_frontend/server.js" || true)

if [ -n "$FLASK_PIDS" ] || [ -n "$NODE_PIDS" ]; then
    echo "⚠️ Found running processes:"
    [ -n "$FLASK_PIDS" ] && ps aux | grep "python.*app.py" | grep -v grep || true
    [ -n "$NODE_PIDS" ] && ps aux | grep "node.*server.js" | grep -v grep || true
    echo ""
    read -p "Kill running processes? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        [ -n "$FLASK_PIDS" ] && echo "$FLASK_PIDS" | xargs kill -9 2>/dev/null || true
        [ -n "$NODE_PIDS" ] && echo "$NODE_PIDS" | xargs kill -9 2>/dev/null || true
        echo "✅ Stopped running processes"
    fi
else
    echo "✅ No running processes found"
fi

# ================================
# Summary
# ================================

echo ""
echo "🎉 Cleanup completed!"
echo "======================================="

if [ ${#FOUND_GROUPS[@]} -gt 0 ] && [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "⏳ Azure resources deletion in progress"
    echo "💰 Costs will stop once deletion completes (~2-5 minutes)"
else
    echo "✅ No Azure resources being deleted"
fi

echo "✅ Local environment cleaned"
echo ""
echo "🚀 To set up again, run:"
if [[ " ${FOUND_GROUPS[@]} " =~ " ${LOCAL_RESOURCE_GROUP} " ]]; then
    echo "   ./deploy-local.sh  (for local development)"
fi
if [[ " ${FOUND_GROUPS[@]} " =~ " ${PROD_RESOURCE_GROUP} " ]]; then
    echo "   ./deploy.sh       (for production)"
fi
echo ""
echo "💡 Your source code is safe - only temporary files were removed"