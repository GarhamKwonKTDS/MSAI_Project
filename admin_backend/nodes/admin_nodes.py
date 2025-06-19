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
- create_case: User wants to create a new case from a description
- update_case: User wants to modify/update case data
- generate_from_unsolved: User wants to create a case from unsolved VoC issues
- unknown: Cannot determine intent

Look for keywords like:
- "Create a case from this description" → create_case
- "Update case data" → update_case
- "Generate from unsolved" → generate_from_unsolved

Respond in JSON format:
{{
    "intent": "one of the above intents",
    "description": "extracted description if any"
}}

Only respond with valid JSON."""

    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content.strip())
        
        state['user_intent'] = result.get('intent', 'unknown')
        state['search_query'] = result.get('description')
        
        logger.info(f"✅ Detected intent: {state['user_intent']}")
        
    except Exception as e:
        logger.error(f"Error in state analyzer: {e}")
        state['user_intent'] = 'unknown'
        state['error'] = str(e)
    
    return state

def handle_request_node(state: AdminChatbotState, llm: AzureChatOpenAI, 
                       search_service, analytics_service) -> AdminChatbotState:
    """
    Handle the user's request and generate case data
    """
    intent = state.get('user_intent', 'unknown')
    logger.info(f"📝 Handling request with intent: {intent}")
    
    try:
        if intent == 'create_case':
            # Generate case data from description
            description = state.get('search_query', state['user_message'])
            
            prompt = f"""Based on this issue description, generate a complete case entry for our knowledge base.

Description: "{description}"

Generate a JSON object with these fields:
- issue_type: Choose from [oss_login_failure, oss_permission_request, oss_information_management]
- issue_name: Korean name for the issue type
- case_type: A unique identifier in snake_case (e.g., password_reset, account_locked)
- case_name: Descriptive name for this specific case
- description: Clear description of the problem
- keywords: Array of relevant search keywords
- symptoms: Array of symptoms users might experience
- questions_to_ask: Array of diagnostic questions
- solution_steps: Array of step-by-step solutions
- escalation_triggers: Array of conditions that require escalation

Example format:
{{
    "issue_type": "oss_login_failure",
    "issue_name": "OSS 로그인 문제",
    "case_type": "password_expired",
    "case_name": "Password Expired",
    "description": "IDMS 비밀번호가 만료되어 OSS 로그인이 불가능한 상황",
    "keywords": ["비밀번호만료", "password expired", "로그인불가"],
    "symptoms": ["비밀번호가 만료되었다는 메시지", "로그인 시도 시 오류"],
    "questions_to_ask": ["언제 마지막으로 비밀번호를 변경하셨나요?", "어떤 오류 메시지가 나타나나요?"],
    "solution_steps": ["1. IDMS 포털에 접속합니다", "2. 비밀번호 재설정을 선택합니다", "3. 새 비밀번호를 설정합니다"],
    "escalation_triggers": ["IDMS 접근 불가", "반복적인 재설정 실패"]
}}

Generate appropriate data based on the description. Respond with ONLY the JSON object."""

            response = llm.invoke(prompt)
            try:
                case_data = json.loads(response.content.strip())
                state['case_data'] = case_data
                state['response'] = json.dumps(case_data, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                state['error'] = "Failed to generate valid case data"
                state['response'] = "Error: Could not generate valid case structure"
                
        elif intent == 'update_case':
            # For updates, we'd need the existing case data and the changes
            state['response'] = "To update a case, please provide the case ID and the changes you want to make."
            
        elif intent == 'generate_from_unsolved':
            # TODO: Integrate with analytics to get unsolved issues
            state['response'] = "Fetching unsolved VoC issues... (This feature will connect to analytics data)"
            
        else:
            state['response'] = "Please describe the issue you want to create a case for, or specify what you want to update."
            
    except Exception as e:
        logger.error(f"Error handling request: {e}")
        state['error'] = str(e)
        state['response'] = f"An error occurred: {str(e)}"
    
    return state