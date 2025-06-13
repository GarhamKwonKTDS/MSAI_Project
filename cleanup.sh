# Daily Cleanup Script
# cleanup.sh

#!/bin/bash

echo "🧹 Starting daily cleanup..."

# Configuration
RESOURCE_GROUP="rg-oss-chatbot-dev"

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
    echo "⚠️ This will delete ALL resources in the resource group!"
    read -p "Continue with cleanup? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️ Deleting resource group and all resources..."
        az group delete --name $RESOURCE_GROUP --yes --no-wait
        
        echo "✅ Cleanup initiated successfully!"
        echo "Resources will be deleted in the background (usually takes 2-5 minutes)"
        echo "💰 All costs will stop accruing once deletion is complete"
    else
        echo "❌ Cleanup cancelled"
        exit 1
    fi
else
    echo "ℹ️ Resource group $RESOURCE_GROUP not found - nothing to clean up"
fi

# ================================
# Clean up local deployment files
# ================================

echo ""
echo "🧹 Cleaning up local deployment files..."

if [ -d "deployment" ]; then
    rm -rf deployment
    echo "  ✅ Removed deployment directory"
fi

if [ -f "deployment.zip" ]; then
    rm deployment.zip
    echo "  ✅ Removed deployment.zip"
fi

if [ -f ".env" ]; then
    rm .env
    echo "  ✅ Removed temporary .env file"
fi

if [ -f "search-config.env" ]; then
    rm search-config.env
    echo "  ✅ Removed search-config.env"
fi

# ================================
# Summary
# ================================

echo ""
echo "🎉 Daily cleanup completed!"
echo "================================"
echo "✅ Azure resources deletion initiated"
echo "✅ Local deployment files cleaned"
echo ""
echo "💡 Tomorrow you can run './deploy.sh' to redeploy everything fresh"
echo "💰 No Azure costs will be incurred overnight"