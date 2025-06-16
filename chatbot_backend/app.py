# app.py - VoC Chatbot Flask Application

import os
import logging
import json
from typing import Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from services.azure_search import search_service
from services.graph_builder import VoCChatbotGraphBuilder

from models.state import create_initial_state
from utils.helpers import validate_config

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# ================================
# Global Variables
# ================================

llm = None
graph_builder = None
conversation_config = None

# ================================
# Configuration
# ================================

class AppConfig:
    """Application configuration"""
    
    def __init__(self):
        # Azure OpenAI settings
        self.azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_openai_key = os.getenv('AZURE_OPENAI_KEY')
        self.azure_openai_model = os.getenv('AZURE_OPENAI_MODEL', 'gpt-4o-mini')
        
        # Azure Search settings
        self.azure_search_endpoint = os.getenv('AZURE_SEARCH_ENDPOINT')
        self.azure_search_key = os.getenv('AZURE_SEARCH_KEY')
        self.azure_search_index = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')

app_config = AppConfig()

# ================================
# Initialization
# ================================

def initialize_application():
    """Initialize all application components"""
    global llm, graph_builder, conversation_config
    
    logger.info("🚀 Initializing VoC Chatbot Application...")
    
    try:
        # 1. Load and validate conversation configuration
        logger.info("🔧 Loading conversation configuration...")
        try:
            with open('configs/conversation_config.json', 'r', encoding='utf-8') as f:
                conversation_config = json.load(f)
            
            if not validate_config(conversation_config):
                raise Exception("Invalid conversation configuration")
            
            logger.info("✅ Configuration loaded and validated")
        except FileNotFoundError:
            logger.error("❌ conversation_config.json not found")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config: {e}")
            return False
        
        # 2. Initialize Azure OpenAI
        if not app_config.azure_openai_endpoint or not app_config.azure_openai_key:
            logger.error("❌ Azure OpenAI credentials not configured")
            return False
        
        llm = AzureChatOpenAI(
            azure_endpoint=app_config.azure_openai_endpoint,
            api_key=app_config.azure_openai_key,
            azure_deployment=app_config.azure_openai_model,
            api_version="2024-02-01",
            temperature=0.3,
            max_tokens=None,
            timeout=30,
            max_retries=2
        )
        logger.info(f"✅ Azure OpenAI initialized: {app_config.azure_openai_model}")
        
        # 3. Initialize Azure Search (optional - just log if not available)
        if search_service.is_available():
            logger.info("✅ Azure AI Search is available")
        else:
            logger.warning("⚠️  Azure AI Search not available - RAG will be disabled")
        
        # 4. Build LangGraph
        graph_builder = VoCChatbotGraphBuilder(conversation_config, llm)
        graph_builder.build_graph()
        
        logger.info("✅ LangGraph built successfully")
        
        logger.info("🎉 VoC Chatbot Application initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Application initialization failed: {e}")
        return False

# ================================
# Routes
# ================================

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy" if graph_builder else "unhealthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """Main chat endpoint"""
    
    if not graph_builder:
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
        
        # Validate input
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        logger.info(f"💬 Chat request - Session: {session_id[:8]}..., Message: {user_message[:50]}...")
        
        # Create initial state
        initial_state = create_initial_state(user_message, session_id)
        
        # Create session config
        session_config = graph_builder.create_session_config(session_id)
        chatbot_graph = graph_builder.get_graph()
        
        # Run the graph
        logger.info("🔄 Running LangGraph workflow...")
        final_state = chatbot_graph.invoke(initial_state, config=session_config)

        logger.info("✅ Workflow completed successfully")
        logger.debug(f"Final state: {final_state}")
        
        # Prepare response
        response = {
            "response": final_state.get("final_response", "죄송합니다. 응답을 생성할 수 없습니다."),
            "session_id": session_id,
            "metadata": {
                "conversation_turn": final_state.get("conversation_turn", 1),
                "current_issue": final_state.get("current_issue"),
                "current_case": final_state.get("current_case"),
                "rag_used": final_state.get("rag_used", False),
                "error_flag": final_state.get("error_flag"),
                "flag": final_state.get("flag")
            }
        }
        
        logger.info("✅ Chat response generated successfully")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"❌ Chat endpoint error: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e) if app.debug else "An error occurred"
        }), 500

# ================================
# Main
# ================================

if __name__ == '__main__':
    # Initialize on startup
    if not initialize_application():
        logger.error("❌ Failed to initialize application")
    
    # Run Flask app
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug)