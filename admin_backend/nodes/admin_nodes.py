# nodes/admin_nodes.py

import logging
import json
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from models.state import AdminChatbotState

logger = logging.getLogger(__name__)

def state_analyzer_node(state: AdminChatbotState, llm: AzureChatOpenAI) -> AdminChatbotState:
    """
    Analyze user intent from the message
    """
    logger.info(f"🔍 Analyzing user message: {state['user_message'][:50]}...")
    
    prompt = f"""Analyze this admin user's message and determine their intent.

User message: "{state['user_message']}"

Possible intents:
- search_cases: User wants to search or find cases/issues
- create_case: User wants to create a new case
- update_case: User wants to update/edit an existing case  
- delete_case: User wants to delete a case
- search_analytics: User wants analytics data or statistics
- unknown: Cannot determine intent

Respond in JSON format:
{{
    "intent": "one of the above intents",
    "search_query": "search query if searching (else null)",
    "case_id": "case ID if updating/deleting (else null)"
}}

Only respond with valid JSON."""

    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content.strip())
        
        state['user_intent'] = result.get('intent', 'unknown')
        state['search_query'] = result.get('search_query')
        state['case_id'] = result.get('case_id')
        
        logger.info(f"✅ Detected intent: {state['user_intent']}")
        
    except Exception as e:
        logger.error(f"Error in state analyzer: {e}")
        state['user_intent'] = 'unknown'
        state['error'] = str(e)
    
    return state

def handle_request_node(state: AdminChatbotState, llm: AzureChatOpenAI, 
                       search_service, analytics_service) -> AdminChatbotState:
    """
    Handle the user's request based on intent
    """
    intent = state.get('user_intent', 'unknown')
    logger.info(f"📝 Handling request with intent: {intent}")
    
    try:
        if intent == 'search_cases':
            query = state.get('search_query', state['user_message'])
            cases = search_service.search_cases(query)
            
            if cases:
                response = f"Found {len(cases)} cases:\n\n"
                for case in cases[:5]:  # Show top 5
                    response += f"• {case['case_name']} ({case['id']})\n"
                    response += f"  {case['description'][:100]}...\n\n"
            else:
                response = "No cases found matching your search."
            
            state['response'] = response
            
        elif intent == 'create_case':
            # For now, just provide instructions
            state['response'] = """To create a new case, please provide the following information:
- Issue Type (e.g., oss_login_failure)
- Issue Name 
- Case Type (unique identifier)
- Case Name
- Description
- Keywords (optional)
- Solution Steps (optional)"""
            
        elif intent == 'update_case':
            case_id = state.get('case_id')
            if case_id:
                case = search_service.get_case(case_id)
                if case:
                    state['response'] = f"Found case {case_id}:\n{json.dumps(case, indent=2, ensure_ascii=False)}\n\nWhat would you like to update?"
                else:
                    state['response'] = f"Case {case_id} not found."
            else:
                state['response'] = "Please specify which case ID you want to update."
                
        elif intent == 'delete_case':
            case_id = state.get('case_id')
            if case_id:
                state['response'] = f"Are you sure you want to delete case {case_id}? Please confirm."
            else:
                state['response'] = "Please specify which case ID you want to delete."
                
        elif intent == 'search_analytics':
            # Simple analytics summary
            state['response'] = "Analytics feature coming soon. Use the analytics endpoints for now."
            
        else:
            state['response'] = "I couldn't understand your request. You can:\n• Search for cases\n• Create a new case\n• Update an existing case\n• Delete a case\n• View analytics"
            
    except Exception as e:
        logger.error(f"Error handling request: {e}")
        state['error'] = str(e)
        state['response'] = f"An error occurred: {str(e)}"
    
    return state