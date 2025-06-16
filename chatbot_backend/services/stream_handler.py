# services/stream_handler.py

import logging
from typing import Dict, Any, AsyncGenerator
from models.state import create_initial_state

logger = logging.getLogger(__name__)

class StreamHandler:
    """
    Handles streaming chat responses through LangGraph
    """
    
    def __init__(self):
        self.graph_builder = None
        self.chatbot_graph = None
    
    def initialize(self, graph_builder, chatbot_graph):
        """Initialize with graph instances from main app"""
        self.graph_builder = graph_builder
        self.chatbot_graph = chatbot_graph
    
    async def process_chat_stream(
        self, 
        user_message: str, 
        session_id: str, 
        is_continuation: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process chat request with streaming updates
        
        Args:
            user_message: User's message
            session_id: Session identifier
            is_continuation: Whether this is a continuation
            
        Yields:
            Dict[str, Any]: Streaming updates
        """
        try:
            # Create session config
            session_config = self.graph_builder.create_session_config(session_id)
            
            # Create initial state
            initial_state = create_initial_state(user_message, session_id)
            
            # Yield start event
            yield {"status": "started", "session_id": session_id}
            
            # For now, use regular invoke (we'll add streaming next)
            yield {"node": "state_analyzer", "status": "processing"}
            
            # Stream events from LangGraph
            final_state = None
            async for event in self.chatbot_graph.astream(initial_state, config=session_config):
                # Get the node name from the event
                if isinstance(event, dict):
                    for node_name, node_state in event.items():
                        if node_name != "__end__":
                            yield {
                                "node": node_name, 
                                "status": "processing",
                                "details": {
                                    "current_issue": node_state.get("current_issue"),
                                    "current_case": node_state.get("current_case"),
                                    "classification_confidence": node_state.get("classification_confidence", 0.0)
                                }
                            }
                            final_state = node_state
            
            # Yield the final response
            if final_state:
                yield {
                    "response": final_state.get("final_response", "죄송합니다. 응답을 생성할 수 없습니다."),
                    "metadata": {
                        "current_issue": final_state.get("current_issue"),
                        "current_case": final_state.get("current_case"),
                        "rag_used": final_state.get("rag_used", False),
                        "question_count": final_state.get("question_count", 0),
                        "nodes_executed": final_state.get("node_history", [])
                    }
                }
            
        except Exception as e:
            logger.error(f"❌ Error in stream processing: {e}")
            yield {"error": str(e)}

# Global instance
stream_handler = StreamHandler()