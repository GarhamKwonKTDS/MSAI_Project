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
        self.conversation_store = None

    def initialize(self, graph_builder, chatbot_graph, conversation_store):
        """Initialize with graph instances from main app"""
        self.graph_builder = graph_builder
        self.chatbot_graph = chatbot_graph
        self.conversation_store = conversation_store

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
            
            # Check for existing state
            existing_state = None
            try:
                state_snapshot = self.chatbot_graph.get_state(session_config)
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
                # Save conversation to Cosmos DB
                self.conversation_store.save_conversation_turn_sync(session_id, final_state)

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
