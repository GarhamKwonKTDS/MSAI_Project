# services/graph_builder.py

import logging
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models.state import ChatbotState

# Import all node functions
from nodes.state_analysis import state_analysis_node,  determine_next_state_analysis
from nodes.issue_classification import issue_classification_node, determine_next_issue_classification
from nodes.case_narrowing import case_narrowing_node
from nodes.reply_formulation import reply_formulation_node

logger = logging.getLogger(__name__)

class VoCChatbotGraphBuilder:
    """
    Builds the LangGraph workflow for the VoC chatbot
    """
    
    def __init__(self, config: Dict[str, Any], llm: AzureChatOpenAI):
        """
        Initialize the graph builder
        
        Args:
            config: Conversation configuration
            llm: Azure OpenAI LLM instance
        """
        self.config = config
        self.llm = llm
        self.graph = None
        self.memory = MemorySaver()
        
    def build_graph(self) -> StateGraph:
        """
        Build the complete LangGraph workflow
        
        Returns:
            StateGraph: Compiled graph
        """
        
        logger.info("🔧 Building VoC Chatbot LangGraph...")
        
        # Initialize StateGraph
        workflow = StateGraph(ChatbotState)
        
        # Add nodes
        self._add_nodes(workflow)
        
        # Set entry point
        workflow.set_entry_point("state_analyzer")
        
        # Configure edges and routing
        self._configure_edges(workflow)
            
        # Compile the graph
        self.graph = workflow.compile(checkpointer=self.memory)
        
        logger.info("✅ VoC Chatbot LangGraph built successfully")
        return self.graph
    
    def _add_nodes(self, workflow: StateGraph) -> None:
        """
        Add all nodes to the workflow
        
        Args:
            workflow: StateGraph instance
        """
        
        # Wrapper functions that bind config and llm to nodes
        def state_analyzer_wrapper(state: ChatbotState) -> ChatbotState:
            return state_analysis_node(state, self.config, self.llm)
        
        def issue_classification_wrapper(state: ChatbotState) -> ChatbotState:
            return issue_classification_node(state, self.config, self.llm)
        
        def case_narrowing_wrapper(state: ChatbotState) -> ChatbotState:
            return case_narrowing_node(state, self.config, self.llm)
        
        def reply_formulation_wrapper(state: ChatbotState) -> ChatbotState:
            return reply_formulation_node(state, self.config, self.llm)
        
        # Add nodes to workflow
        workflow.add_node("state_analyzer", state_analyzer_wrapper)
        workflow.add_node("issue_classification", issue_classification_wrapper)
        workflow.add_node("case_narrowing", case_narrowing_wrapper)
        workflow.add_node("reply_formulation", reply_formulation_wrapper)
        
        logger.info("   📋 Added all workflow nodes")

    def _configure_edges(self, workflow: StateGraph) -> None:
        """
        Configure all edges and conditional routing
        
        Args:
            workflow: StateGraph instance
        """
        
        # State analyzer routing
        workflow.add_conditional_edges(
            "state_analyzer",
            determine_next_state_analysis,
            {
                "issue_classification": "issue_classification",
                "case_narrowing": "case_narrowing"
            }
        )
        
        # Issue classification routing
        workflow.add_conditional_edges(
            "issue_classification",
            determine_next_issue_classification,
            {
                "case_narrowing": "case_narrowing",
                "reply_formulation": "reply_formulation"
            }
        )
        
        # Case narrowing always goes to reply formulation
        workflow.add_edge("case_narrowing", "reply_formulation")
        
        # Reply formulation always ends
        workflow.add_edge("reply_formulation", END)
        
        logger.info("   🔗 Configured all workflow edges")
    
    def get_graph(self) -> StateGraph:
        """
        Get the compiled graph (build if not already built)
        
        Returns:
            StateGraph: Compiled graph
        """
        if self.graph is None:
            self.build_graph()
        return self.graph

    def create_session_config(self, session_id: str) -> Dict[str, Any]:
        """
        Create session configuration for LangGraph
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict: Session configuration
        """
        return {
            "configurable": {
                "thread_id": session_id
            }
        }