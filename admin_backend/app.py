# admin_backend/admin_app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from datetime import datetime
from typing import Dict, Any, List

# Azure imports
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.cosmos import CosmosClient
from azure.core.credentials import AzureKeyCredential

from analytics import run_conversation_processing, run_analytics

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AZURE_SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_ENDPOINT')
AZURE_SEARCH_KEY = os.getenv('AZURE_SEARCH_KEY')
AZURE_SEARCH_INDEX = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')

COSMOS_ENDPOINT = os.getenv('COSMOS_ENDPOINT')
COSMOS_KEY = os.getenv('COSMOS_KEY')
COSMOS_DATABASE = os.getenv('COSMOS_DATABASE', 'voc-chatbot')
COSMOS_CONTAINER = os.getenv('COSMOS_CONTAINER', 'conversations')

# Initialize clients
search_client = None
cosmos_client = None

def initialize_clients():
    """Initialize Azure service clients"""
    global search_client, cosmos_client
    
    try:
        # Azure Search
        if AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY:
            search_client = SearchClient(
                endpoint=AZURE_SEARCH_ENDPOINT,
                index_name=AZURE_SEARCH_INDEX,
                credential=AzureKeyCredential(AZURE_SEARCH_KEY)
            )
            logger.info("✅ Azure Search client initialized")
        
        # Cosmos DB
        if COSMOS_ENDPOINT and COSMOS_KEY:
            cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
            logger.info("✅ Cosmos DB client initialized")
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize clients: {e}")

# Initialize on startup
initialize_clients()

# ================================
# Analytics Endpoints
# ================================

@app.route('/api/analytics/summary')
def get_analytics_summary():
    """Get overall metrics summary"""
    try:
        # TODO: Implement Cosmos DB query for metrics
        # For now, return mock data
        summary = {
            "total_sessions": 156,
            "active_sessions_today": 23,
            "avg_response_time": 2.4,
            "success_rate": 0.78,
            "total_escalations": 34,
            "timestamp": datetime.now().isoformat()
        }
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics/issues')
def get_issue_breakdown():
    """Get issue classification breakdown"""
    try:
        # TODO: Implement Cosmos DB aggregation
        # For now, return mock data
        breakdown = {
            "issues": [
                {"issue_type": "oss_login_failure", "count": 89, "percentage": 0.57},
                {"issue_type": "oss_permission_request", "count": 45, "percentage": 0.29},
                {"issue_type": "oss_information_management", "count": 22, "percentage": 0.14}
            ],
            "total": 156,
            "timestamp": datetime.now().isoformat()
        }
        return jsonify(breakdown)
    except Exception as e:
        logger.error(f"Issue breakdown error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/process-conversations', methods=['POST'])
def process_conversations_http():
    """
    HTTP endpoint for conversation processing
    """
    logging.info('Conversation processing HTTP trigger executed.')

    try:
        result = run_conversation_processing()
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Conversation processing failed: {str(e)}")
        return jsonify({
            "error": f"Conversation processing failed: {str(e)}"
        }), 500

@app.route('/analytics', methods=['POST'])
def analytics_http():
    """
    HTTP endpoint for analytics execution
    """
    logging.info('Analytics HTTP trigger executed.')

    try:
        result = run_analytics()
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Analytics failed: {str(e)}")
        return jsonify({
            "error": f"Analytics failed: {str(e)}"
        }), 500

# ================================
# Knowledge Base Endpoints
# ================================

@app.route('/api/knowledge/cases')
def get_all_cases():
    """List all cases from Azure Search"""
    try:
        if not search_client:
            return jsonify({"error": "Search service not available"}), 503
        
        results = search_client.search(
            search_text="*",
            select=["id", "issue_type", "issue_name", "case_type", "case_name", "description"],
            top=100
        )
        
        cases = []
        for result in results:
            cases.append({
                "id": result.get("id"),
                "issue_type": result.get("issue_type"),
                "issue_name": result.get("issue_name"),
                "case_type": result.get("case_type"),
                "case_name": result.get("case_name"),
                "description": result.get("description")
            })
        
        return jsonify({"cases": cases, "count": len(cases)})
        
    except Exception as e:
        logger.error(f"Get cases error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge/cases/<case_id>')
def get_case(case_id: str):
    """Get specific case details"""
    try:
        if not search_client:
            return jsonify({"error": "Search service not available"}), 503
        
        result = search_client.get_document(key=case_id)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Get case error: {e}")
        return jsonify({"error": "Case not found"}), 404

@app.route('/api/knowledge/cases', methods=['POST'])
def create_case():
    """Create new case"""
    try:
        if not search_client:
            return jsonify({"error": "Search service not available"}), 503
        
        case_data = request.get_json()
        
        # Validate required fields
        required_fields = ["id", "issue_type", "issue_name", "case_type", "case_name"]
        for field in required_fields:
            if field not in case_data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Upload to Azure Search
        result = search_client.upload_documents(documents=[case_data])
        
        if result[0].succeeded:
            return jsonify({"message": "Case created successfully", "id": case_data["id"]}), 201
        else:
            return jsonify({"error": "Failed to create case"}), 500
            
    except Exception as e:
        logger.error(f"Create case error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge/cases/<case_id>', methods=['PUT'])
def update_case(case_id: str):
    """Update existing case"""
    try:
        if not search_client:
            return jsonify({"error": "Search service not available"}), 503
        
        case_data = request.get_json()
        case_data["id"] = case_id  # Ensure ID matches
        
        # Merge/update in Azure Search
        result = search_client.merge_or_upload_documents(documents=[case_data])
        
        if result[0].succeeded:
            return jsonify({"message": "Case updated successfully"})
        else:
            return jsonify({"error": "Failed to update case"}), 500
            
    except Exception as e:
        logger.error(f"Update case error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge/cases/<case_id>', methods=['DELETE'])
def delete_case(case_id: str):
    """Delete case"""
    try:
        if not search_client:
            return jsonify({"error": "Search service not available"}), 503
        
        result = search_client.delete_documents(documents=[{"id": case_id}])
        
        if result[0].succeeded:
            return jsonify({"message": "Case deleted successfully"})
        else:
            return jsonify({"error": "Failed to delete case"}), 500
            
    except Exception as e:
        logger.error(f"Delete case error: {e}")
        return jsonify({"error": str(e)}), 500

# ================================
# Health Check
# ================================

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "services": {
            "azure_search": search_client is not None,
            "cosmos_db": cosmos_client is not None
        },
        "timestamp": datetime.now().isoformat()
    })

# ================================
# Main Entry Point
# ================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8082))
    debug_mode = os.getenv('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"🚀 Starting Admin Backend on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)