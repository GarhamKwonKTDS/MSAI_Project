# state.py
from typing import TypedDict, Optional, Dict, Any

# Admin Chatbot State
class AdminChatbotState(TypedDict):
    """State for admin chatbot"""
    user_message: str
    user_intent: Optional[str]  # search_cases, create_case, update_case, delete_case, search_analytics
    search_query: Optional[str]
    case_data: Optional[Dict[str, Any]]
    case_id: Optional[str]
    response: str
    error: Optional[str]