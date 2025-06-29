# app.py - VoC Chatbot Flask Application

import os
import logging
import json
import asyncio
from typing import Dict, Any
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

from models.state import create_initial_state
from utils.helpers import validate_config, format_sse, sanitize_user_input

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
# Global Variables
# ================================

from services.azure_search import AzureSearchService
from services.graph_builder import VoCChatbotGraphBuilder
from services.stream_handler import StreamHandler
from services.cosmos_store import ConversationStore

llm = None
graph_builder = None
conversation_config = None
search_service = None
stream_handler = None
conversation_store = None

# ================================
# Initialization
# ================================

def initialize_application():
    """Initialize all application components"""
    global llm, graph_builder, conversation_config, search_service, stream_handler, conversation_store
    
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
        search_service = AzureSearchService()

        if search_service.is_available():
            logger.info("✅ Azure AI Search is available")
        else:
            logger.warning("⚠️  Azure AI Search not available - RAG will be disabled")

        # 4. Initialize Cosmos DB store (optional - just log if not available)
        conversation_store = ConversationStore()

        if conversation_store.is_available():
            logger.info("✅ Cosmos DB conversation store initialized")
        else:
            logger.warning("⚠️  Cosmos DB not available - conversation storage will be disabled")
        
        # 5. Build LangGraph
        graph_builder = VoCChatbotGraphBuilder(conversation_config, llm, search_service)
        chatbot_graph = graph_builder.build_graph()
        
        logger.info("✅ LangGraph built successfully")

        # Initialize stream handler with graph instances
        stream_handler = StreamHandler()

        stream_handler.initialize(graph_builder, chatbot_graph, conversation_store)
        logger.info("✅ Stream handler initialized")
        
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
        
        # Create session config
        session_config = graph_builder.create_session_config(session_id)
        chatbot_graph = graph_builder.get_graph()
        
        # Check for existing state
        existing_state = None
        try:
            state_snapshot = chatbot_graph.get_state(session_config)
            if state_snapshot and state_snapshot.values:
                existing_state = state_snapshot.values
                logger.info(f"✅ Retrieved existing state for session {session_id[:8]}...")
                logger.info(f"   Current issue: {existing_state.get('current_issue')}")
                logger.info(f"   Current case: {existing_state.get('current_case')}")
        except Exception as e:
            logger.info(f"ℹ️ No existing state found for session {session_id[:8]}...")
        
        # Create or update state
        if existing_state:
            # Update existing state with new message
            initial_state = existing_state.copy()
            initial_state['user_message'] = user_message
            initial_state['conversation_history'].append({
                "role": "user",
                "content": user_message
            })
            initial_state['conversation_turn'] = initial_state.get('conversation_turn', 0) + 1
        else:
            # Create new initial state
            initial_state = create_initial_state(user_message, session_id)
        
        # Run the graph
        logger.info("🔄 Running LangGraph workflow...")
        final_state = chatbot_graph.invoke(initial_state, config=session_config)

        # Save conversation turn to Cosmos DB
        conversation_store.save_conversation_turn_sync(session_id, final_state)

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

@app.route('/chat/stream', methods=['POST'])
def chat_stream_endpoint():
    """Streaming chat endpoint for real-time updates"""
    
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
        
        # Sanitize user input
        user_message = sanitize_user_input(user_message)
        if not user_message:
            return jsonify({"error": "Invalid message content"}), 400
        
        logger.info(f"💬 Stream request - Session: {session_id[:8]}..., Message: {user_message[:50]}...")
        
        # Create generator for streaming
        def generate():
            # Create event loop for async processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run async generator in sync context
                async_gen = stream_handler.process_chat_stream(user_message, session_id)
                
                while True:
                    try:
                        update = loop.run_until_complete(async_gen.__anext__())
                        
                        # Determine event type based on content
                        if "error" in update:
                            yield format_sse(update, "error")
                        elif "response" in update:
                            yield format_sse(update, "complete")
                        elif "node" in update:
                            yield format_sse(update, "progress")
                        else:
                            yield format_sse(update, "update")
                            
                    except StopAsyncIteration:
                        break
                        
            finally:
                loop.close()
        
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Stream endpoint error: {e}")
        return jsonify({
            "error": "Internal server error",
            "code": "INTERNAL_ERROR"
        }), 500

# ================================
# Main
# ================================

if not initialize_application():
    logger.error("❌ Failed to initialize application")
else:
    logger.info("✅ Application initialized successfully")

if __name__ == '__main__':
    
    # Run Flask app locally
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug)