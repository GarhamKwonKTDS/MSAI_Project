# admin_backend/app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from datetime import datetime
from typing import Dict, Any, List

# Import services
from services.analytics import AnalyticsService
from services.azure_search import AzureSearchService
from services.graph_builder import AdminChatbotGraphBuilder

# Import state
from models.state import AdminChatbotState

# Azure imports
from langchain_openai import AzureChatOpenAI

# Import Cosmos DB client
from azure.cosmos import CosmosClient

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services and clients
search_service = None
analytics_service = None
admin_chatbot_graph = None
cosmos_client = None

def initialize_services():
    """Initialize all services and clients"""
    global search_service, analytics_service, admin_chatbot_graph, cosmos_client
    
    try:
        # Initialize search service
        search_service = AzureSearchService()
        
        # Initialize analytics service
        analytics_service = AnalyticsService()
        
        # Initialize Cosmos DB client (for existing endpoints)
        COSMOS_ENDPOINT = os.getenv('AZURE_COSMOS_ENDPOINT')
        COSMOS_KEY = os.getenv('AZURE_COSMOS_KEY')
        if COSMOS_ENDPOINT and COSMOS_KEY:
            cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
            logger.info("✅ Cosmos DB client initialized")
        
        # Initialize LLM for chatbot
        if os.getenv('AZURE_OPENAI_ENDPOINT') and os.getenv('AZURE_OPENAI_KEY'):
            llm = AzureChatOpenAI(
                azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
                api_key=os.getenv('AZURE_OPENAI_KEY'),
                azure_deployment=os.getenv('AZURE_OPENAI_MODEL', 'gpt-4o-mini'),
                api_version="2024-02-01",
                temperature=0.3
            )
            
            # Build admin chatbot graph
            graph_builder = AdminChatbotGraphBuilder(llm, search_service, analytics_service)
            admin_chatbot_graph = graph_builder.build_graph()
            logger.info("✅ Admin chatbot initialized")
        
        logger.info("✅ All services initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")

# Initialize on startup
initialize_services()

# ================================
# Analytics Endpoints
# ================================

@app.route('/process-conversations', methods=['POST'])
def process_conversations_http():
    """
    HTTP endpoint for conversation processing
    """
    logging.info('Conversation processing HTTP trigger executed.')

    try:
        if not analytics_service:
            return jsonify({"error": "Analytics service not available"}), 503
            
        result = analytics_service.run_conversation_processing()
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
        if not analytics_service:
            return jsonify({"error": "Analytics service not available"}), 503
            
        result = analytics_service.run_analytics()
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Analytics failed: {str(e)}")
        return jsonify({
            "error": f"Analytics failed: {str(e)}"
        }), 500
    
@app.route('/api/analytics/summary')
def get_analytics_summary():
    """Get overall metrics summary from the latest analytics run"""
    try:
        if not cosmos_client:
            return jsonify({"error": "Cosmos DB not available"}), 503
        
        database_name = os.getenv('AZURE_COSMOS_DATABASE', 'voc-analytics')

        # Get database and statistics container
        database = cosmos_client.get_database_client(database_name)
        statistics_container = database.get_container_client('statistics')
        
        # Query for the most recent overall summary
        query = """
        SELECT TOP 1 * FROM c 
        WHERE c.type = 'overall_summary' 
        ORDER BY c.generated_at DESC
        """
        
        summaries = list(statistics_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not summaries:
            # No analytics data yet - return default values
            return jsonify({
                "message": "No analytics data available yet",
                "timestamp": datetime.now().isoformat()
            })
        
        latest_summary = summaries[0]
        metrics = latest_summary.get('metrics', {})
        
        # Return the full metrics structure
        return jsonify({
            "metrics": metrics,
            "generated_at": latest_summary.get('generated_at', datetime.now().isoformat()),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        return jsonify({"error": str(e)}), 500

# ================================
# Admin Chatbot Endpoint
# ================================

@app.route('/api/admin/chat', methods=['POST'])
def admin_chat():
    """Admin chatbot endpoint for knowledge base management"""
    if not admin_chatbot_graph:
        return jsonify({"error": "Admin chatbot not available"}), 503
    
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f"admin_{datetime.now().timestamp()}")
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        logger.info(f"💬 Admin chat - Session: {session_id[:8]}..., Message: {user_message[:50]}...")
        
        # Create initial state
        initial_state = AdminChatbotState(
            user_message=user_message,
            user_intent=None,
            search_query=None,
            case_data=None,
            case_id=None,
            response="",
            error=None
        )
        
        # Run the graph
        config = {"configurable": {"thread_id": session_id}}
        final_state = admin_chatbot_graph.invoke(initial_state, config=config)
        
        # Build response with case data if generated
        response_data = {
            "response": final_state.get("response", "Sorry, I couldn't process your request."),
            "intent": final_state.get("user_intent"),
            "session_id": session_id
        }
        
        # Include case_data if it was generated
        if final_state.get("case_data"):
            response_data["case_data"] = final_state["case_data"]
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Admin chat error: {e}")
        return jsonify({"error": str(e)}), 500

# ================================
# Knowledge Base Endpoints
# ================================

@app.route('/api/knowledge/cases')
def get_all_cases():
    """List all cases from Azure Search"""
    try:
        if not search_service or not search_service.is_available():
            return jsonify({"error": "Search service not available"}), 503
        
        cases = search_service.search_cases("*", top_k=100)
        
        return jsonify({"cases": cases, "count": len(cases)})
        
    except Exception as e:
        logger.error(f"Get cases error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge/cases/<case_id>')
def get_case(case_id: str):
    """Get specific case details"""
    try:
        if not search_service or not search_service.is_available():
            return jsonify({"error": "Search service not available"}), 503
        
        case = search_service.get_case(case_id)
        if case:
            return jsonify(case)
        else:
            return jsonify({"error": "Case not found"}), 404
        
    except Exception as e:
        logger.error(f"Get case error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge/cases', methods=['POST'])
def create_case():
    """Create new case"""
    try:
        if not search_service or not search_service.is_available():
            return jsonify({"error": "Search service not available"}), 503
        
        case_data = request.get_json()
        
        # Validate required fields
        required_fields = ["id", "issue_type", "issue_name", "case_type", "case_name"]
        for field in required_fields:
            if field not in case_data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Create case
        success = search_service.create_case(case_data)
        
        if success:
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
        if not search_service or not search_service.is_available():
            return jsonify({"error": "Search service not available"}), 503
        
        case_data = request.get_json()
        
        # Update case
        success = search_service.update_case(case_id, case_data)
        
        if success:
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
        if not search_service or not search_service.is_available():
            return jsonify({"error": "Search service not available"}), 503
        
        success = search_service.delete_case(case_id)
        
        if success:
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
            "azure_search": search_service is not None,
            "cosmos_db": cosmos_client is not None,
            "analytics_service": analytics_service is not None,
            "admin_chatbot_graph": admin_chatbot_graph is not None
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