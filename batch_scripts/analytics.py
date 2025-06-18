import os
import logging
from datetime import datetime
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnalyticsProcessor:
    def __init__(self):
        """Initialize Cosmos DB client"""
        self.cosmos_endpoint = os.getenv('AZURE_COSMOS_ENDPOINT')
        self.cosmos_key = os.getenv('AZURE_COSMOS_KEY')
        self.database_name = os.getenv('AZURE_COSMOS_DATABASE', 'voc-chatbot')
        
        # Container names
        self.conversations_container = 'conversations'
        self.statistics_container = 'statistics'
        
        # Initialize Cosmos client
        self.client = CosmosClient(self.cosmos_endpoint, self.cosmos_key)
        self.database = self.client.get_database_client(self.database_name)
        
        logger.info(f"✅ Connected to Cosmos DB: {self.database_name}")
    
    def fetch_all_conversations(self):
        """Fetch all conversations from the database"""
        try:
            container = self.database.get_container_client(self.conversations_container)
            
            # Simple query to get all conversations
            query = "SELECT * FROM c"
            
            conversations = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            logger.info(f"📊 Found {len(conversations)} total conversations")
            return conversations
            
        except Exception as e:
            logger.error(f"❌ Error fetching conversations: {e}")
            return []
    
    def calculate_overall_metrics(self, conversations):
        """Calculate overall metrics for all conversations"""
        if not conversations:
            logger.warning("⚠️ No conversations found")
            return self._empty_metrics()
        
        # Initialize counters
        total_conversations = len(conversations)
        total_messages = 0
        unique_sessions = set()
        
        # Performance metrics
        solved_count = 0
        escalated_count = 0
        abandoned_count = 0
        interrupted_count = 0
        
        # Duration and turns for averages
        durations = []
        turns = []
        
        # Issue and case distribution
        issue_types = defaultdict(int)
        case_types = defaultdict(int)
        
        # Unidentified cases
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
            
            # Check for unidentified cases
            if not issue_type and not case_type:
                unidentified_conversations.append(conv.get('id', 'unknown'))
        
        # Calculate averages
        avg_duration = sum(durations) / len(durations) if durations else 0
        avg_turns = sum(turns) / len(turns) if turns else 0
        success_rate = (solved_count / total_conversations * 100) if total_conversations > 0 else 0
        
        metrics = {
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
                "conversation_ids": unidentified_conversations[:10]  # Limit to first 10 for readability
            }
        }
        
        logger.info("✅ Metrics calculated successfully")
        return metrics
            
    def _empty_metrics(self):
        """Return empty metrics structure when no conversations found"""
        return {
            "volume": {
                "total_conversations": 0,
                "total_messages": 0,
                "unique_sessions": 0
            },
            "performance": {
                "success_rate": 0,
                "breakdown": {
                    "solved": 0,
                    "escalated": 0,
                    "abandoned": 0,
                    "interrupted": 0
                },
                "avg_conversation_length": 0,
                "avg_resolution_time_minutes": 0
            },
            "issue_distribution": {},
            "case_distribution": {},
            "unidentified": {
                "count": 0,
                "conversation_ids": []
            }
        }
    
    def save_overall_summary(self, metrics):
        """Save the overall summary to the statistics container"""
        try:
            container = self.database.get_container_client(self.statistics_container)
            
            summary = {
                "id": f"overall_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "type": "overall_summary",
                "date": datetime.now().strftime('%Y-%m-%d'),  # Partition key
                "metrics": metrics,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            container.create_item(summary)
            logger.info(f"✅ Saved overall summary with ID: {summary['id']}")
            
        except Exception as e:
            logger.error(f"❌ Error saving overall summary: {e}")
            raise
    
    def print_summary(self, metrics):
        """Print a readable summary to console"""
        print("\n" + "="*60)
        print("📊 CONVERSATION ANALYTICS SUMMARY")
        print("="*60)
        
        # Volume metrics
        volume = metrics['volume']
        print(f"\n📈 VOLUME METRICS:")
        print(f"   Total Conversations: {volume['total_conversations']:,}")
        print(f"   Total Messages: {volume['total_messages']:,}")
        print(f"   Unique Sessions: {volume['unique_sessions']:,}")
        
        # Performance metrics
        perf = metrics['performance']
        print(f"\n⚡ PERFORMANCE METRICS:")
        print(f"   Success Rate: {perf['success_rate']}%")
        print(f"   Average Conversation Length: {perf['avg_conversation_length']} turns")
        print(f"   Average Resolution Time: {perf['avg_resolution_time_minutes']} minutes")
        
        print(f"\n📊 STATUS BREAKDOWN:")
        breakdown = perf['breakdown']
        for status, count in breakdown.items():
            print(f"   {status.title()}: {count}")
        
        # Issue distribution
        if metrics['issue_distribution']:
            print(f"\n🔍 TOP ISSUE TYPES:")
            sorted_issues = sorted(metrics['issue_distribution'].items(), key=lambda x: x[1], reverse=True)
            for issue, count in sorted_issues[:5]:  # Top 5
                print(f"   {issue}: {count}")
        
        # Case distribution
        if metrics['case_distribution']:
            print(f"\n📋 TOP CASE TYPES:")
            sorted_cases = sorted(metrics['case_distribution'].items(), key=lambda x: x[1], reverse=True)
            for case, count in sorted_cases[:5]:  # Top 5
                print(f"   {case}: {count}")
        
        # Unidentified
        unidentified = metrics['unidentified']
        if unidentified['count'] > 0:
            print(f"\n⚠️ UNIDENTIFIED CASES: {unidentified['count']}")
            if unidentified['conversation_ids']:
                print(f"   Sample IDs: {', '.join(unidentified['conversation_ids'][:3])}")
        
        print("="*60)

def main():
    """Main execution function"""
    try:
        # Initialize processor
        processor = AnalyticsProcessor()
        
        # Fetch all conversations
        logger.info("🔄 Fetching all conversations...")
        conversations = processor.fetch_all_conversations()
        
        if not conversations:
            logger.warning("⚠️ No conversations found. Exiting.")
            return
        
        # Calculate metrics
        logger.info("🔄 Calculating metrics...")
        metrics = processor.calculate_overall_metrics(conversations)
        
        # Print summary to console
        processor.print_summary(metrics)
        
        # Save to database
        logger.info("🔄 Saving summary to database...")
        processor.save_overall_summary(metrics)
        
        logger.info("✅ Analytics processing completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Process failed: {e}")
        raise

if __name__ == "__main__":
    main()