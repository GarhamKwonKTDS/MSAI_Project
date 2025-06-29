# admin_backend/services/analytics.py

import os
import logging
from datetime import datetime, timedelta, timezone
from azure.cosmos import CosmosClient
from collections import defaultdict

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for handling analytics operations"""
    
    def __init__(self):
        self.cosmos_endpoint = os.environ.get('AZURE_COSMOS_ENDPOINT')
        self.cosmos_key = os.environ.get('AZURE_COSMOS_KEY')
        self.database_name = os.environ.get('AZURE_COSMOS_DATABASE', 'voc-analytics')
        
        if self.cosmos_endpoint and self.cosmos_key:
            self.client = CosmosClient(self.cosmos_endpoint, self.cosmos_key)
            self.database = self.client.get_database_client(self.database_name)
        else:
            logger.warning("Cosmos DB credentials not found")
            self.client = None
            self.database = None

    def run_conversation_processing(self):
        """Main conversation processing logic"""
        # Initialize Cosmos DB client
        cosmos_endpoint = os.environ['AZURE_COSMOS_ENDPOINT']
        cosmos_key = os.environ['AZURE_COSMOS_KEY']
        database_name = os.environ.get('AZURE_COSMOS_DATABASE', 'voc-analytics')
        
        client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = client.get_database_client(database_name)
        
        # Define time window (process last 15 minutes to align with timer)
        end_time = datetime.now(timezone.utc) - timedelta(minutes=5)  # 5 min buffer
        start_time = end_time - timedelta(minutes=15)
        
        logger.info(f"Processing window: {start_time} to {end_time}")
        
        # Fetch turns in this window
        turns_container = database.get_container_client('turns')
        
        query = """
        SELECT * FROM c 
        WHERE c.timestamp >= @start_time 
        AND c.timestamp <= @end_time
        """
        
        parameters = [
            {"name": "@start_time", "value": start_time.isoformat()},
            {"name": "@end_time", "value": end_time.isoformat()}
        ]
        
        turns = list(turns_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        logger.info(f"Found {len(turns)} turns to process")
        
        if not turns:
            return {"message": "No turns found in time window", "processed": 0}
        
        # Get distinct sessions
        session_ids = set()
        for turn in turns:
            session_id = turn.get('session_id')
            if session_id:
                session_ids.add(session_id)
        
        logger.info(f"Found {len(session_ids)} distinct sessions")
        
        # Process each session
        saved_count = 0
        conversations_container = database.get_container_client('conversations')
        
        for session_id in session_ids:
            try:
                # Fetch all turns for this session
                session_query = "SELECT * FROM c WHERE c.session_id = @session_id"
                session_params = [{"name": "@session_id", "value": session_id}]
                
                session_turns = list(turns_container.query_items(
                    query=session_query,
                    parameters=session_params,
                    enable_cross_partition_query=True
                ))
                
                # Analyze conversation
                conversation_data = self.analyze_conversation(session_turns)
                
                if conversation_data:
                    # Save to conversations container
                    conversation_data['processed_at'] = datetime.utcnow().isoformat()
                    conversations_container.upsert_item(conversation_data)
                    saved_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing session {session_id}: {str(e)}")
                continue
        
        return {
            "message": "Conversation processing completed",
            "turns_found": len(turns),
            "sessions_processed": len(session_ids),
            "conversations_saved": saved_count
        }

    def analyze_conversation(self, turns):
        """Analyze conversation turns and extract key information"""
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
        
        # Find issue and case_type
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
            if turn.get('user_message'):
                message_history.append({
                    'type': 'user',
                    'message': turn['user_message'],
                    'timestamp': turn.get('timestamp'),
                    'turn': turn.get('conversation_turn', 0)
                })
            
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
            'message_count': len(turns) * 2,
            'message_history': message_history
        }
        
        return conversation_data

    # ============================================================================
    # ANALYTICS FUNCTIONS
    # ============================================================================

    def run_analytics(self):
        """Main analytics logic"""
        # Initialize Cosmos DB client
        cosmos_endpoint = os.environ['AZURE_COSMOS_ENDPOINT']
        cosmos_key = os.environ['AZURE_COSMOS_KEY']
        database_name = os.environ.get('AZURE_COSMOS_DATABASE', 'voc-analytics')
        
        client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = client.get_database_client(database_name)
        
        # Fetch all conversations
        conversations_container = database.get_container_client('conversations')
        conversations = list(conversations_container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        ))
        
        logger.info(f"Found {len(conversations)} conversations for analytics")
        
        if not conversations:
            return {"message": "No conversations found", "metrics": None}
        
        # Calculate metrics
        metrics = self.calculate_analytics_metrics(conversations)
        
        # Save summary
        statistics_container = database.get_container_client('statistics')
        summary = {
            "id": f"overall_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "type": "overall_summary",
            "date": datetime.utcnow().strftime('%Y-%m-%d'),
            "metrics": metrics,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        statistics_container.create_item(summary)
        
        return {
            "message": "Analytics completed successfully",
            "summary_id": summary["id"],
            "conversations_processed": len(conversations),
            "metrics": metrics
        }

    def calculate_analytics_metrics(self, conversations):
        """Calculate metrics for conversations"""
        total_conversations = len(conversations)
        total_messages = 0
        unique_sessions = set()
        
        # Performance counters
        solved_count = 0
        escalated_count = 0
        abandoned_count = 0
        interrupted_count = 0
        
        # For averages
        durations = []
        turns = []
        
        # Distribution counters
        issue_types = defaultdict(int)
        case_types = defaultdict(int)
        unidentified_conversations = []
        
        # Process each conversation
        for conv in conversations:
            # Volume metrics
            total_messages += conv.get('message_count', 0)
            if conv.get('session_id'):
                unique_sessions.add(conv['session_id'])
            
            # Performance metrics
            status = conv.get('conversation_result', '').lower()
            if status == 'solved':
                solved_count += 1
            elif status == 'escalated':
                escalated_count += 1
            elif status == 'abandoned':
                abandoned_count += 1
            elif status == 'interrupted':
                interrupted_count += 1
            
            # Duration and turns
            if conv.get('duration'):
                durations.append(conv['duration'])
            if conv.get('total_turns'):
                turns.append(conv['total_turns'])
            
            # Issue distribution
            issue_type = conv.get('issue')
            if issue_type:
                issue_types[issue_type] += 1
            
            case_type = conv.get('case')
            if case_type:
                case_types[case_type] += 1
            
            # Unidentified cases
            if not issue_type and not case_type:
                unidentified_conversations.append(conv.get('id', 'unknown'))
        
        # Calculate averages
        avg_duration = sum(durations) / len(durations) if durations else 0
        avg_turns = sum(turns) / len(turns) if turns else 0
        success_rate = (solved_count / total_conversations * 100) if total_conversations > 0 else 0
        
        return {
            "volume": {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "unique_sessions": len(unique_sessions)
            },
            "performance": {
                "success_rate": round(success_rate, 2),
                "breakdown": {
                    "solved": solved_count,
                    "escalated": escalated_count,
                    "abandoned": abandoned_count,
                    "interrupted": interrupted_count
                },
                "avg_conversation_length": round(avg_turns, 2),
                "avg_resolution_time_minutes": round(avg_duration, 2)
            },
            "issue_distribution": dict(issue_types),
            "case_distribution": dict(case_types),
            "unidentified": {
                "count": len(unidentified_conversations),
                "conversation_ids": unidentified_conversations[:10]
            }
        }