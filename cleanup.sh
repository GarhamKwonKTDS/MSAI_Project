#!/bin/bash

echo "🧹 Starting cleanup..."

# ================================
# Detect which resource groups exist
# ================================

RESOURCE_GROUP_PREFIX="rg-oss-chatbot-dev"
FOUND_GROUPS=()

echo "🔍 Checking for Azure resource groups..."

# Get all resource groups and filter by prefix
ALL_GROUPS=$(az group list --query "[].name" --output tsv 2>/dev/null || echo "")

if [ -n "$ALL_GROUPS" ]; then
    # Find groups starting with our prefix
    MATCHING_GROUPS=$(echo "$ALL_GROUPS" | grep "^${RESOURCE_GROUP_PREFIX}" || true)
    if [ -n "$MATCHING_GROUPS" ]; then
        while IFS= read -r group; do
            echo "  ✓ Found resource group: $group"
            FOUND_GROUPS+=("$group")
        done <<< "$MATCHING_GROUPS"
    fi
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
echo "  - Deployment directories (deployment_*, admin_*_deployment/)"
echo "  - Deployment packages (*.zip)"
echo "  - Environment files (.env, *.env, local.settings.json)"
echo "  - Virtual environment (venv/)"
echo "  - Configuration files (services-config.json, apps-config.json, local-dev-info.json)"
echo "  - Development scripts (run-*.sh, test-*.sh)"
echo "  - Log files (*.log)"
echo "  - Python cache (__pycache__)"
echo "  - Deployment info files (*deployment-info.json)"
echo ""
read -p "Clean up local files? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    
    # Remove all deployment directories
    for dir in deployment deployment_* admin_*_deployment frontend_deployment backend_deployment; do
        if [ -d "$dir" ]; then
            rm -rf "$dir"
            echo "  ✅ Removed $dir/"
        fi
    done

    # Remove zip files
    if ls *.zip 1> /dev/null 2>&1; then
        rm *.zip
        echo "  ✅ Removed deployment zip files"
    fi
    
    # Remove all environment files
    for env_file in .env *.env local.settings.json; do
        if [ -f "$env_file" ]; then
            rm "$env_file"
            echo "  ✅ Removed $env_file"
        fi
    done
    
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
    
    # Remove all config files
    for config_file in services-config.json apps-config.json local-dev-info.json *deployment-info.json; do
        if [ -f "$config_file" ]; then
            rm "$config_file"
            echo "  ✅ Removed $config_file"
        fi
    done
    
    # Remove all development scripts
    for script in run-*.sh test-*.sh; do
        if [ -f "$script" ]; then
            rm "$script"
            echo "  ✅ Removed $script"
        fi
    done

    echo ""
    echo "✅ Local files cleaned up"
    
else
    echo "⏭️ Keeping local files"
fi

# ================================
# Check for running processes
# ================================

# echo ""
# echo "🔍 Checking for running processes..."

# # Check for any Python processes running app.py
# PYTHON_PIDS=$(pgrep -f "python.*app.py" || true)
# # Check for any Node processes running server.js
# NODE_PIDS=$(pgrep -f "node.*server.js" || true)
# # Check for Azure Functions
# FUNC_PIDS=$(pgrep -f "func.*start" || true)

# if [ -n "$PYTHON_PIDS" ] || [ -n "$NODE_PIDS" ] || [ -n "$FUNC_PIDS" ]; then
#     echo "⚠️ Found running processes:"
#     [ -n "$PYTHON_PIDS" ] && ps aux | grep "python.*app.py" | grep -v grep || true
#     [ -n "$NODE_PIDS" ] && ps aux | grep "node.*server.js" | grep -v grep || true
#     [ -n "$FUNC_PIDS" ] && ps aux | grep "func.*start" | grep -v grep || true
#     echo ""
#     read -p "Kill running processes? (y/n): " -n 1 -r
#     echo
#     if [[ $REPLY =~ ^[Yy]$ ]]; then
#         [ -n "$PYTHON_PIDS" ] && echo "$PYTHON_PIDS" | xargs kill -9 2>/dev/null || true
#         [ -n "$NODE_PIDS" ] && echo "$NODE_PIDS" | xargs kill -9 2>/dev/null || true
#         [ -n "$FUNC_PIDS" ] && echo "$FUNC_PIDS" | xargs kill -9 2>/dev/null || true
#         echo "✅ Stopped running processes"
#     fi
# else
#     echo "✅ No running processes found"
# fi

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
echo "   1. ./deploy_services.sh    (to create Azure services)"
echo "   2. ./deploy_apps.sh        (to deploy apps to Azure)"
echo "   3. ./deploy_local.sh       (to set up local development)"
echo ""
echo "💡 Your source code is safe - only temporary files were removed"