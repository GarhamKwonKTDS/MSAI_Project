# services/cosmos_store.py

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
from azure.cosmos import CosmosClient, PartitionKey, exceptions

logger = logging.getLogger(__name__)

class ConversationStore:
    """
    Azure Cosmos DB service for storing conversation data
    """
    
    def __init__(self):
        """Initialize Cosmos DB client"""
        self.endpoint = os.getenv('AZURE_COSMOS_ENDPOINT')
        self.key = os.getenv('AZURE_COSMOS_KEY')
        self.database_name = os.getenv('AZURE_COSMOS_DATABASE', 'voc-analytics')
        self.container_name = os.getenv('AZURE_COSMOS_TURNS_CONTAINER', 'turns')
        
        if not self.endpoint or not self.key:
            logger.warning("Cosmos DB credentials not found - conversation storage will be disabled")
            self.client = None
            self.container = None
            return
            
        try:
            self.client = CosmosClient(self.endpoint, self.key)
            database = self.client.get_database_client(self.database_name)
            self.container = database.get_container_client(self.container_name)
            logger.info(f"✅ Cosmos DB initialized: {self.database_name}/{self.container_name}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Cosmos DB: {e}")
            self.client = None
            self.container = None
    
    def is_available(self) -> bool:
        """Check if Cosmos DB service is available"""
        return self.container is not None
    
    async def save_conversation_turn(self, session_id: str, state: Dict[str, Any]) -> Optional[str]:
        """
        Save a conversation turn to Cosmos DB
        
        Args:
            session_id: Session identifier
            state: Current chatbot state
            
        Returns:
            Optional[str]: Document ID if saved successfully
        """
        if not self.container:
            return None
            
        try:
            document = {
                'id': str(uuid.uuid4()),
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat(),
                'turn_number': state.get('conversation_turn', 1),
                'user_message': state.get('user_message', ''),
                'bot_response': state.get('final_response', ''),
                'current_issue': state.get('current_issue'),
                'current_case': state.get('current_case'),
                'classification_confidence': state.get('classification_confidence', 0.0),
                'rag_used': state.get('rag_used', False),
                'needs_escalation': state.get('needs_escalation', False),
                'escalation_reason': state.get('escalation_reason'),
                'questions_asked': state.get('question_count', 0),
                'solution_provided': state.get('resolution_attempted', False),
                'node_path': state.get('node_history', []),
                'error_occurred': state.get('error_count', 0) > 0,
                'metadata': {
                    'last_node': state.get('last_node', ''),
                    'gathered_info_count': len(state.get('gathered_info', {})),
                    'search_queries': state.get('search_queries', [])
                },
                'processed': False  # For batch processing
            }
            
            response = self.container.create_item(body=document)
            logger.info(f"💾 Saved conversation turn: {response['id']}")
            return response['id']
            
        except Exception as e:
            logger.error(f"❌ Error saving conversation turn: {e}")
            return None
        
    def save_conversation_turn_sync(self, session_id: str, state: Dict[str, Any]) -> Optional[str]:
        """
        Synchronous wrapper for save_conversation_turn - saves in background without blocking
        
        Args:
            session_id: Session identifier
            state: Current chatbot state
            
        Returns:
            Optional[str]: Always returns None since this is fire-and-forget
        """
        logger.info(f"Saving conversation turn for session {session_id[:8]}...")
        if not self.is_available():
            return None
            
        try:
            # Get the current event loop
            loop = asyncio.get_event_loop()
            # Create a task to run in the background (fire-and-forget)
            task = loop.create_task(self.save_conversation_turn(session_id, state))
            
            # Optional: Add error handling callback
            def handle_task_result(task):
                try:
                    result = task.result()
                    if result:
                        logger.debug(f"✅ Background save completed: {result}")
                except Exception as e:
                    logger.error(f"❌ Background save failed: {e}")
            
            task.add_done_callback(handle_task_result)
            
            # Return None since this is fire-and-forget
            return None
        except Exception as e:
            logger.error(f"❌ Failed to save conversation: {e}")
            return None
