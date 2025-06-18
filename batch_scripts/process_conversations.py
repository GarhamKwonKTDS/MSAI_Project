# batch_scripts/process_conversations.py

import os
import logging
from datetime import datetime, timedelta, timezone
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConversationProcessor:
    def __init__(self):
        """Initialize Cosmos DB client"""
        self.cosmos_endpoint = os.getenv('AZURE_COSMOS_ENDPOINT')
        self.cosmos_key = os.getenv('AZURE_COSMOS_KEY')
        self.database_name = os.getenv('AZURE_COSMOS_DATABASE', 'voc-chatbot')
        
        # Container names
        self.turns_container = 'turns'
        self.conversations_container = 'conversations'
        
        # Initialize Cosmos client
        self.client = CosmosClient(self.cosmos_endpoint, self.cosmos_key)
        self.database = self.client.get_database_client(self.database_name)
        
        logger.info(f"✅ Connected to Cosmos DB: {self.database_name}")
    
    def test_connection(self):
        """Test the connection by listing containers"""
        try:
            containers = list(self.database.list_containers())
            logger.info(f"📦 Found {len(containers)} containers:")
            for container in containers:
                logger.info(f"   - {container['id']}")
            return True
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
        
    def fetch_turns_in_window(self, start_time, end_time):
        """Fetch conversation turns within a specific time window"""
        try:
            container = self.database.get_container_client(self.turns_container)
            
            query = """
            SELECT * FROM c 
            WHERE c.timestamp >= @start_time 
            AND c.timestamp <= @end_time
            """
            
            parameters = [
                {"name": "@start_time", "value": start_time.isoformat()},
                {"name": "@end_time", "value": end_time.isoformat()}
            ]
            
            turns = list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            logger.info(f"📊 Fetched {len(turns)} turns between {start_time} and {end_time}")
            
            # Show sample turn structure if we found any
            if turns:
                logger.info(f"📋 Sample turn keys: {list(turns[0].keys())}")
            
            return turns
            
        except Exception as e:
            logger.error(f"❌ Error fetching turns: {e}")
            return []
    def get_distinct_sessions(self, turns):
        """Extract distinct session IDs from turns"""
        session_ids = set()
        
        for turn in turns:
            session_id = turn.get('session_id')
            if session_id:
                session_ids.add(session_id)
        
        logger.info(f"📋 Found {len(session_ids)} distinct sessions")
        return list(session_ids)

    def fetch_full_session(self, session_id):
        """Fetch all turns for a specific session"""
        try:
            container = self.database.get_container_client(self.turns_container)
            
            query = """
            SELECT * FROM c 
            WHERE c.session_id = @session_id
            """
            
            parameters = [
                {"name": "@session_id", "value": session_id}
            ]
            
            turns = list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            logger.info(f"   Session {session_id}: {len(turns)} total turns")
            return turns
            
        except Exception as e:
            logger.error(f"❌ Error fetching session {session_id}: {e}")
            return []
    
    def analyze_conversation(self, turns):
        """Analyze a conversation (all turns from a session) and extract key information"""
        if not turns:
            return None
        
        # Sort by timestamp
        sorted_turns = sorted(turns, key=lambda x: x.get('timestamp', ''))
        
        first_turn = sorted_turns[0]
        last_turn = sorted_turns[-1]
        
        # Determine conversation result
        result = "interrupted"  # default
        if last_turn.get('current_case'):
            result = "solved"
        elif len(turns) < 3:
            result = "abandoned"
        
        # Find issue and case_type (from the last turn that has them)
        issue = None
        case_type = None
        for turn in reversed(sorted_turns):
            if not issue and turn.get('current_issue'):
                issue = turn['current_issue']
            if not case_type and turn.get('current_case'):
                case_type = turn['current_case']
            if issue and case_type:
                break
        # Extract message history
        message_history = []
        for turn in sorted_turns:
            # Add user message
            if turn.get('user_message'):
                message_history.append({
                    'type': 'user',
                    'message': turn['user_message'],
                    'timestamp': turn.get('timestamp'),
                    'turn': turn.get('conversation_turn', 0)
                })
            
            # Add bot response
            message_history.append({
                'type': 'bot',
                'message': turn['bot_response'],
                'timestamp': turn.get('timestamp'),
                'turn': turn.get('conversation_turn', 0)
            })

        # Build conversation data
        conversation_data = {
            'id': f"{first_turn.get('session_id')}_{first_turn.get('timestamp')}",
            'session_id': first_turn.get('session_id'),
            'start_time': first_turn.get('timestamp'),
            'end_time': last_turn.get('timestamp'),
            'issue': issue,
            'case': case_type,
            'conversation_result': result,
            'total_turns': len(turns),
            'message_count': len(turns) * 2,  # user + bot messages
            'message_history': message_history
        }
        
        logger.info(f"   Analyzed: {result}, {issue or 'no issue'}, {case_type or 'no case'}, {len(turns)} turns")
        
        return conversation_data
    
    def save_conversation(self, conversation_data):
        """Save processed conversation to Cosmos DB"""
        try:
            container = self.database.get_container_client(self.conversations_container)
            
            # Add processing timestamp
            conversation_data['processed_at'] = datetime.utcnow().isoformat()
            
            # Upsert the conversation
            result = container.upsert_item(conversation_data)
            
            logger.info(f"   ✅ Saved conversation: {conversation_data['id']}")
            return True
            
        except Exception as e:
            logger.error(f"   ❌ Error saving conversation: {e}")
            return False

def main():
    """Main execution function"""
    try:
        # Initialize processor
        processor = ConversationProcessor()
        
        # Test connection
        if processor.test_connection():
            logger.info("✅ Connection successful!")
            
            # Define time window (30 minutes buffer to avoid in-progress conversations)
            buffer_minutes = 0
            end_time = datetime.now(timezone.utc) - timedelta(minutes=buffer_minutes)
            start_time = end_time - timedelta(hours=24)  # Process last 24 hours
            
            logger.info(f"🕐 Processing window: {start_time} to {end_time}")
            
            # Fetch turns in this window
            turns = processor.fetch_turns_in_window(start_time, end_time)
            logger.info(f"📝 Found {len(turns)} turns to process")

            if turns:
                # Get distinct sessions
                session_ids = processor.get_distinct_sessions(turns)
                
                # Process each session
                saved_count = 0
                for session_id in session_ids[:3]:  # Process first 3 for testing
                    logger.info(f"\n🔍 Processing session: {session_id}")
                    full_session = processor.fetch_full_session(session_id)

                    conversation_data = processor.analyze_conversation(full_session)
    
                    if conversation_data:
                        # Save to Cosmos DB
                        if processor.save_conversation(conversation_data):
                            saved_count += 1
                
                logger.info(f"\n✅ Saved {saved_count} conversations")
        
    except Exception as e:
        logger.error(f"❌ Process failed: {e}")
        raise

if __name__ == "__main__":
    main()