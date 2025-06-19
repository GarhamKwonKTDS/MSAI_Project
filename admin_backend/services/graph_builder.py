# admin_backend/services/graph_builder.py

import logging
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models.state import AdminChatbotState
from nodes.admin_nodes import state_analyzer_node, handle_request_node

logger = logging.getLogger(__name__)

class AdminChatbotGraphBuilder:
    """Builds the LangGraph workflow for admin chatbot"""
    
    def __init__(self, llm: AzureChatOpenAI, search_service, analytics_service):
        """
        Initialize the graph builder
        
        Args:
            llm: Azure OpenAI LLM instance
            search_service: Azure Search service instance
            analytics_service: Analytics service instance
        """
        self.llm = llm
        self.search_service = search_service
        self.analytics_service = analytics_service
        self.graph = None
        self.memory = MemorySaver()
        
    def build_graph(self) -> StateGraph:
        """
        Build the admin chatbot workflow
        
        Returns:
            StateGraph: Compiled graph
        """
        logger.info("🔧 Building Admin Chatbot LangGraph...")
        
        # Initialize StateGraph
        workflow = StateGraph(AdminChatbotState)
        
        # Add nodes with bound services
        workflow.add_node(
            "state_analyzer", 
            lambda state: state_analyzer_node(state, self.llm)
        )
        workflow.add_node(
            "handle_request",
            lambda state: handle_request_node(
                state, self.llm, self.search_service, self.analytics_service
            )
        )
        
        # Set entry point
        workflow.set_entry_point("state_analyzer")
        
        # Configure edges
        workflow.add_edge("state_analyzer", "handle_request")
        workflow.add_edge("handle_request", END)
        
        # Compile the graph
        self.graph = workflow.compile(checkpointer=self.memory)
        
        logger.info("✅ Admin Chatbot LangGraph built successfully")
        return self.graph
    
    def get_graph(self) -> StateGraph:
        """Get the compiled graph"""
        if self.graph is None:
            self.build_graph()
        return self.graph
    
    def create_session_config(self, session_id: str) -> Dict[str, Any]:
        """Create session configuration"""
        return {
            "configurable": {
                "thread_id": session_id
            }
        }