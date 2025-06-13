# Flask App - API Only (No Client-Side Code)
# app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import logging
from typing import Dict, List, Optional, TypedDict
from dataclasses import dataclass

# LangChain imports - Updated for newer versions
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Azure Search imports (for RAG)
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# Configuration Management
# ================================

# Load environment variables for local testing
from dotenv import load_dotenv
load_dotenv()

@dataclass
class Config:
    # Azure OpenAI settings (we're using Azure only)
    azure_openai_endpoint: str = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_openai_key: str = os.getenv('AZURE_OPENAI_KEY') 
    azure_openai_model: str = os.getenv('AZURE_OPENAI_MODEL', 'gpt-4o-mini')
    
    # Azure AI Search (RAG)
    azure_search_endpoint: str = os.getenv('AZURE_SEARCH_ENDPOINT')
    azure_search_key: str = os.getenv('AZURE_SEARCH_KEY')
    azure_search_index: str = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')
    
    # App settings
    max_conversation_turns: int = 10
    rag_enabled: bool = os.getenv('RAG_ENABLED', 'true').lower() == 'true'
    rag_top_k: int = int(os.getenv('RAG_TOP_K', '3'))

config = Config()

# ================================
# State Definition
# ================================

class ChatbotState(TypedDict):
    """챗봇의 상태를 관리하는 State 클래스"""
    user_message: str
    conversation_history: List[Dict[str, str]]
    current_issue: Optional[str]
    current_case: Optional[str]
    classification_confidence: float
    gathered_info: Dict[str, str]
    questions_asked: List[str]
    question_count: int
    solution_ready: bool
    final_response: str
    needs_escalation: bool
    conversation_turn: int
    last_node: str
    retrieved_cases: List[Dict]
    rag_context: str
    rag_used: bool

def create_initial_state(user_message: str) -> ChatbotState:
    """초기 상태를 생성하는 헬퍼 함수"""
    return {
        "user_message": user_message,
        "conversation_history": [],
        "current_issue": None,
        "current_case": None,
        "classification_confidence": 0.0,
        "gathered_info": {},
        "questions_asked": [],
        "question_count": 0,
        "solution_ready": False,
        "final_response": "",
        "needs_escalation": False,
        "conversation_turn": 1,
        "last_node": "",
        "retrieved_cases": [],
        "rag_context": "",
        "rag_used": False
    }

# ================================
# Global Variables
# ================================

llm = None
search_client = None
issues_config = None
conversation_config = None
chatbot_app = None

# ================================
# Simple Fallback Configurations
# ================================

def get_fallback_configs():
    """Minimal fallback configurations"""
    issues = {
        "issues": {
            "oss_login_failure": {
                "name": "OSS 로그인 문제",
                "description": "OSS/NEOSS 로그인 관련 모든 문제",
                "cases": {
                    "general": {
                        "name": "일반 로그인 문제",
                        "case_identification_prompt": "로그인 관련 일반적인 문제",
                        "information_gathering": {
                            "key_questions": ["어떤 오류 메시지가 나타나나요?", "언제부터 로그인이 안 되셨나요?"]
                        },
                        "solution_framework": {
                            "assessment_prompt": "로그인 문제를 해결해드리겠습니다."
                        }
                    }
                }
            }
        }
    }
    
    conversation = {
        "conversation_flow": {
            "issue_classification": {
                "prompt_template": "사용자 메시지: {user_message}\n\n이 메시지가 어떤 문제에 관한 것인지 분석해주세요."
            },
            "case_narrowing": {
                "max_questions_per_case": 4
            },
            "solution_delivery": {
                "follow_up_strategy": "추가 도움이 필요하시면 말씀해주세요."
            }
        },
        "fallback_responses": {
            "escalation": "전문 상담원에게 연결해드리겠습니다.",
            "general_error": "죄송합니다. 오류가 발생했습니다."
        }
    }
    
    return issues, conversation

# ================================
# Service Initialization
# ================================

def initialize_services():
    """모든 서비스 초기화"""
    global llm, search_client, issues_config, conversation_config
    
    logger.info("🚀 Starting service initialization...")
    
    # Load configurations
    try:
        with open('issues_config.json', 'r', encoding='utf-8') as f:
            issues_config = json.load(f)
        with open('conversation_config.json', 'r', encoding='utf-8') as f:
            conversation_config = json.load(f)
        logger.info("✅ Loaded config files")
    except Exception as e:
        logger.warning(f"⚠️ Config files not found, using fallback: {e}")
        issues_config, conversation_config = get_fallback_configs()
    
    # Azure OpenAI 초기화 - Updated for newer library version
    if not config.azure_openai_endpoint or not config.azure_openai_key:
        raise Exception("Azure OpenAI configuration missing!")
    
    try:
        llm = AzureChatOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_key,
            azure_deployment=config.azure_openai_model,
            api_version="2024-02-01",  # Updated API version
            temperature=0.3,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )
        logger.info(f"✅ Azure OpenAI initialized: {config.azure_openai_model}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Azure OpenAI: {e}")
        raise
    
    # Azure AI Search 초기화 (optional)
    if config.azure_search_endpoint and config.azure_search_key:
        try:
            search_client = SearchClient(
                endpoint=config.azure_search_endpoint,
                index_name=config.azure_search_index,
                credential=AzureKeyCredential(config.azure_search_key)
            )
            logger.info("✅ Azure AI Search initialized")
        except Exception as e:
            logger.warning(f"⚠️ Azure AI Search initialization failed: {e}")

# ================================
# Simplified Node Functions
# ================================

def simple_response_node(state: ChatbotState) -> ChatbotState:
    """Simplified response node for testing"""
    logger.info("🎯 Simple response node")
    
    try:
        # Create a simple prompt
        prompt = f"""당신은 OSS 지원 챗봇입니다. 사용자의 메시지에 친절하게 응답하세요.

사용자 메시지: {state['user_message']}

응답:"""
        
        # Get response from LLM - Updated method call
        response = llm.invoke(prompt)
        state['final_response'] = response.content
        
        # Add RAG context if available
        if search_client and state.get('user_message'):
            try:
                results = search_client.search(
                    search_text=state['user_message'],
                    top=3
                )
                
                contexts = []
                for result in results:
                    contexts.append(f"- {result.get('case_name', '')}: {result.get('description', '')}")
                
                if contexts:
                    state['final_response'] += "\n\n관련 정보:\n" + "\n".join(contexts)
                    state['rag_used'] = True
                    
            except Exception as e:
                logger.warning(f"RAG search failed: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error in response generation: {e}")
        state['final_response'] = "죄송합니다. 응답 생성 중 오류가 발생했습니다."
    
    return state

# ================================
# Create Simple Chatbot Graph
# ================================

def create_simple_chatbot_graph():
    """Create a simplified graph for testing"""
    logger.info("🔧 Creating simple chatbot graph...")
    
    workflow = StateGraph(ChatbotState)
    workflow.add_node("respond", simple_response_node)
    workflow.set_entry_point("respond")
    workflow.add_edge("respond", END)
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    logger.info("✅ Simple chatbot graph created")
    return app

# ================================
# Flask Routes (API Only)
# ================================

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "services": {
            "azure_openai": llm is not None,
            "azure_search": search_client is not None,
            "chatbot_app": chatbot_app is not None
        },
        "versions": {
            "langchain": ">=0.1.17",
            "langchain-openai": ">=0.1.6",
            "openai": ">=1.55.3"
        }
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        logger.info(f"💬 Chat request - Session: {session_id}, Message: {user_message[:50]}...")
        
        # Check if chatbot is initialized
        if chatbot_app is None:
            logger.error("❌ Chatbot app is not initialized!")
            return jsonify({"error": "Chatbot not initialized"}), 500
        
        # Create initial state and run graph
        initial_state = create_initial_state(user_message)
        config_dict = {"configurable": {"thread_id": session_id}}
        
        try:
            final_state = chatbot_app.invoke(initial_state, config=config_dict)
            
            response = {
                "response": final_state.get("final_response", "응답을 생성할 수 없습니다."),
                "session_id": session_id,
                "rag_used": final_state.get("rag_used", False)
            }
            
            logger.info(f"✅ Response generated successfully")
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"❌ Error running chatbot graph: {e}")
            return jsonify({"error": f"처리 중 오류가 발생했습니다: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"❌ Chat endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ================================
# Initialize Everything at Module Level
# ================================

logger.info("🚀 Initializing OSS Chatbot Application...")

try:
    # Initialize services
    initialize_services()
    
    # Create chatbot graph
    chatbot_app = create_simple_chatbot_graph()
    
    logger.info("🎉 OSS Chatbot Application initialized successfully!")
    
except Exception as e:
    logger.error(f"❌ Failed to initialize application: {e}")
    logger.error("Running in degraded mode - chat will not work")

# ================================
# Main Entry Point
# ================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_ENV', 'production') == 'development'
    
    # Check if running locally
    if not config.azure_openai_endpoint and debug_mode:
        print("⚠️  WARNING: Azure OpenAI credentials not found!")
        print("📝 To run locally, create a .env file with:")
        print("   AZURE_OPENAI_ENDPOINT=your_endpoint")
        print("   AZURE_OPENAI_KEY=your_key")
        print("   AZURE_OPENAI_MODEL=gpt-4o-mini")
        print("   AZURE_SEARCH_ENDPOINT=your_search_endpoint (optional)")
        print("   AZURE_SEARCH_KEY=your_search_key (optional)")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)