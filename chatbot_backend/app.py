# app.py - Robust LangGraph VoC Chatbot Flask Application

import os
import logging
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

# Import our modular components
from models.state import ChatbotState, create_initial_state
from services.azure_search import search_service
from services.graph_builder import get_graph_builder
from utils.helpers import (
    load_conversation_config, 
    validate_config, 
    format_error_response,
    sanitize_user_input,
    log_conversation_analytics,
    create_session_summary
)

# LangChain imports
from langchain_openai import AzureChatOpenAI

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================================
# Configuration and Initialization
# ================================

class AppConfig:
    """Application configuration"""
    
    def __init__(self):
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Azure OpenAI settings
        self.azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_openai_key = os.getenv('AZURE_OPENAI_KEY')
        self.azure_openai_model = os.getenv('AZURE_OPENAI_MODEL', 'gpt-4o-mini')
        
        # Azure AI Search settings
        self.azure_search_endpoint = os.getenv('AZURE_SEARCH_ENDPOINT')
        self.azure_search_key = os.getenv('AZURE_SEARCH_KEY')
        self.azure_search_index = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')
        
        # App settings
        self.max_conversation_turns = int(os.getenv('MAX_CONVERSATION_TURNS', '20'))
        self.debug = os.getenv('FLASK_ENV', 'production') == 'development'

# Global variables
app_config = AppConfig()
conversation_config = None
llm = None
graph_builder = None
chatbot_graph = None

def initialize_application():
    """Initialize all application components"""
    global conversation_config, llm, graph_builder, chatbot_graph
    
    logger.info("🚀 Initializing VoC Chatbot Application...")
    
    try:
        # 1. Load conversation configuration
        conversation_config = load_conversation_config()
        if not validate_config(conversation_config):
            raise Exception("Invalid conversation configuration")
        logger.info("✅ Conversation configuration loaded and validated")
        
        # 2. Initialize Azure OpenAI
        if not app_config.azure_openai_endpoint or not app_config.azure_openai_key:
            raise Exception("Azure OpenAI credentials not configured")
        
        llm = AzureChatOpenAI(
            azure_endpoint=app_config.azure_openai_endpoint,
            api_key=app_config.azure_openai_key,
            azure_deployment=app_config.azure_openai_model,
            api_version="2024-02-01",
            temperature=0.3,
            max_tokens=None,
            timeout=30,
            max_retries=2,
        )
        logger.info(f"✅ Azure OpenAI initialized: {app_config.azure_openai_model}")
        
        # 3. Verify Azure Search availability
        if search_service.is_available():
            logger.info("✅ Azure AI Search is available")
        else:
            logger.warning("⚠️ Azure AI Search is not available - RAG will be disabled")
        
        # 4. Build LangGraph
        graph_builder = get_graph_builder(conversation_config, llm)
        chatbot_graph = graph_builder.get_graph()
        
        if graph_builder.validate_graph():
            logger.info("✅ LangGraph validation passed")
        else:
            logger.warning("⚠️ LangGraph validation failed")
        
        logger.info("🎉 VoC Chatbot Application initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Application initialization failed: {e}")
        return False

# ================================
# Flask Routes
# ================================

@app.route('/health')
def health_check():
    """Health check endpoint"""
    
    health_status = {
        "status": "healthy" if chatbot_graph else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "azure_openai": llm is not None,
            "azure_search": search_service.is_available(),
            "langgraph": chatbot_graph is not None,
            "conversation_config": conversation_config is not None
        },
        "configuration": {
            "azure_openai_model": app_config.azure_openai_model,
            "search_index": app_config.azure_search_index,
            "max_turns": app_config.max_conversation_turns
        }
    }
    
    status_code = 200 if chatbot_graph else 503
    return jsonify(health_status), status_code

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """Main chat endpoint for VoC support"""
    
    if not chatbot_graph:
        return jsonify({
            "error": "Chatbot service is not available",
            "code": "SERVICE_UNAVAILABLE"
        }), 503
    
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f"session_{datetime.now().timestamp()}")
        is_continuation = data.get('is_continuation', False)
        
        # Validate input
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        # Sanitize user input
        user_message = sanitize_user_input(user_message)
        if not user_message:
            return jsonify({"error": "Invalid message content"}), 400
        
        logger.info(f"💬 Chat request - Session: {session_id[:8]}..., Message: {user_message[:50]}...")
        
        # Process chat request
        response = process_chat_request(user_message, session_id, is_continuation)
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"❌ Chat endpoint error: {e}")
        return jsonify({
            "error": "Internal server error",
            "code": "INTERNAL_ERROR"
        }), 500

def process_chat_request(user_message: str, session_id: str, is_continuation: bool) -> Dict[str, Any]:
    """
    Process chat request through LangGraph workflow
    
    Args:
        user_message: User's message
        session_id: Session identifier  
        is_continuation: Whether this is a continuation of existing conversation
        
    Returns:
        Dict[str, Any]: Chat response
    """
    
    try:
        # Create session config
        session_config = graph_builder.create_session_config(session_id)
        
        if is_continuation:
            # Handle continuation - retrieve existing state and update
            # This would typically involve loading the last state from memory
            # For now, we'll create a new state with the user response
            initial_state = create_initial_state(user_message, session_id)
            # In a real implementation, you'd load the previous state here
            
        else:
            # New conversation
            initial_state = create_initial_state(user_message, session_id)
        
        # Run the LangGraph workflow
        logger.info(f"🔄 Running LangGraph workflow...")
        final_state = chatbot_graph.invoke(initial_state, config=session_config)
        
        # Log analytics
        log_conversation_analytics(final_state, conversation_config)
        
        # Prepare response
        response = {
            "response": final_state.get("final_response", "죄송합니다. 응답을 생성할 수 없습니다."),
            "session_id": session_id,
            "metadata": {
                "conversation_turn": final_state.get("conversation_turn", 1),
                "current_issue": final_state.get("current_issue"),
                "current_case": final_state.get("current_case"),
                "classification_confidence": final_state.get("classification_confidence", 0.0),
                "questions_asked": final_state.get("question_count", 0),
                "rag_used": final_state.get("rag_used", False),
                "needs_escalation": final_state.get("needs_escalation", False),
                "escalation_reason": final_state.get("escalation_reason"),
                "last_node": final_state.get("last_node", "")
            }
        }
        
        # Add continuation flag if more interaction is expected
        if not final_state.get("needs_escalation") and not final_state.get("resolution_attempted"):
            response["expects_response"] = True
        
        logger.info(f"✅ Chat response generated - Turn: {final_state.get('conversation_turn')}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error processing chat request: {e}")
        
        # Return error response with fallback message
        error_response = format_error_response("general", conversation_config)
        return {
            "response": error_response,
            "session_id": session_id,
            "error": True,
            "metadata": {
                "error_type": "processing_error",
                "error_message": str(e)
            }
        }

@app.route('/session/<session_id>/summary', methods=['GET'])
def get_session_summary(session_id: str):
    """Get session summary and analytics"""
    
    try:
        # In a real implementation, you'd retrieve the session state from storage
        # For now, return a placeholder response
        
        summary = {
            "session_id": session_id,
            "status": "Session summary endpoint - implementation needed",
            "note": "This would retrieve session state from LangGraph memory and provide analytics"
        }
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"❌ Error getting session summary: {e}")
        return jsonify({"error": "Failed to get session summary"}), 500

@app.route('/config', methods=['GET'])
def get_configuration():
    """Get current configuration (for debugging)"""
    
    if not app_config.debug:
        return jsonify({"error": "Configuration access disabled in production"}), 403
    
    config_info = {
        "conversation_config_loaded": conversation_config is not None,
        "azure_services": {
            "openai_configured": bool(app_config.azure_openai_endpoint),
            "search_configured": bool(app_config.azure_search_endpoint),
            "search_available": search_service.is_available()
        },
        "graph_status": {
            "graph_built": chatbot_graph is not None,
            "validation_passed": graph_builder.validate_graph() if graph_builder else False
        }
    }
    
    return jsonify(config_info)

# ================================
# Error Handlers
# ================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# ================================
# Application Startup
# ================================

# Initialize the application when module is loaded
if not initialize_application():
    logger.error("❌ Failed to initialize application - running in degraded mode")

# ================================
# Main Entry Point
# ================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug_mode = app_config.debug
    
    if debug_mode:
        logger.info("🔧 Running in debug mode")
    
    # Final check before starting
    if not chatbot_graph:
        logger.warning("⚠️ Starting server without functional chatbot - check configuration")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)