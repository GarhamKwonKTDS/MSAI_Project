# nodes/state_analysis.py

import logging
import json
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata

logger = logging.getLogger(__name__)

def state_analysis_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    State Analyzer Node - Analyzes current conversation state and determines routing
    
    Args:
        state: Current chatbot state
        config: Conversation configuration
        
    Returns:
        ChatbotState: Updated state
    """
    
    # Update metadata to track this node execution
    state = update_state_metadata(state, "state_analyzer")
    
    logger.info(f"🔍 State Analyzer - Turn {state['conversation_turn']}")
    logger.info(f"   Session: {state['session_id']}")

    # Reset flags at the start of each flow
    state['flag'] = None
    state['error_flag'] = None

    # Check if there's an active conversation to continue
    if state.get('current_issue') or state.get('current_case'):
        # Use LLM to determine if user is continuing or changing topic
        is_continuation = _check_topic_continuity(state, config, llm)
        
        if not is_continuation:
            # Reset conversation state for new topic
            state = _reset_conversation_state(state)
            logger.info("   → New topic detected, resetting state")
    
    return state


def determine_next_state_analysis(state: ChatbotState) -> str:
    """
    Determines the next node based on state analysis
    Used by LangGraph conditional_edges
    
    Args:
        state: Current chatbot state
        
    Returns:
        str: Name of next node to execute
    """
    
    logger.info(f"   Current Issue: {state.get('current_issue')}")
    logger.info(f"   Current Case: {state.get('current_case')}")
    
    # Route based on conversation progress only
    if not state.get('current_issue'):
        # No issue identified yet
        logger.info("   → Routing to: issue_classification")
        return "issue_classification"
    
    else:
        # Issue identified, need to narrow down case
        # (If case was already identified, we would have given solution already)
        logger.info("   → Routing to: case_narrowing")
        return "case_narrowing"

def _check_topic_continuity(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> bool:
    """
    Uses LLM to determine if user message continues the current conversation
    
    Args:
        state: Current chatbot state
        config: Conversation configuration
        llm: LLM instance
        
    Returns:
        bool: True if continuation, False if new topic
    """
    
    # Build context from current conversation
    context_parts = []
    
    if state.get('current_issue'):
        context_parts.append(f"현재 다루고 있는 문제: {state['current_issue']}")
    
    if state.get('current_case'):
        context_parts.append(f"구체적인 케이스: {state['current_case']}")
    
    # Add recent conversation history
    if state.get('conversation_history'):
        recent = state['conversation_history'][-2:]  # Last 2 turns
        for turn in recent:
            context_parts.append(f"사용자: {turn.get('user', '')}")
            context_parts.append(f"봇: {turn.get('bot', '')[:100]}...")
    
    # Get prompt from config
    prompt_template = config['conversation_flow']['state_analysis']['topic_continuity_prompt']
    json_instruction = config['conversation_flow']['common']['json_parse_instruction']
    
    prompt = prompt_template.format(
        context=chr(10).join(context_parts),
        user_message=state['user_message']
    ) + "\n\n" + json_instruction

    try:
        response = llm.invoke(prompt)
        result_json = json.loads(response.content.strip())
        
        is_continuation = result_json.get('is_continuation', True)
        reason = result_json.get('reason', '')
        
        logger.info(f"   Topic continuity: {'Continuation' if is_continuation else 'New topic'}")
        logger.info(f"   Reason: {reason}")
        
        return is_continuation
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in topic continuity: {e}")
        state['error_flag'] = 'json_parse_error'
        return True  # Default to continuation
    except Exception as e:
        logger.error(f"Topic continuity check error: {e}")
        state['error_flag'] = 'llm_error'
        return True # Default to continuation

def _reset_conversation_state(state: ChatbotState) -> ChatbotState:
    """
    Resets conversation state for a new topic
    
    Args:
        state: Current chatbot state
        
    Returns:
        ChatbotState: State with reset conversation fields
    """
    
    logger.info("   🔄 Resetting conversation state for new topic")
    
    # Reset issue/case identification
    state['current_issue'] = None
    state['current_case'] = None
    state['classification_confidence'] = 0.0
    state['classification_attempts'] = 0
    
    # Reset information gathering
    state['gathered_info'] = {}
    state['questions_asked'] = []
    state['question_count'] = 0
    state['pending_question'] = None
    
    # Reset solution state
    state['solution_ready'] = False
    state['resolution_attempted'] = False
    
    # Reset RAG/search data
    state['retrieved_cases'] = []
    state['rag_context'] = ""
    state['search_queries'] = []
    
    # Keep session metadata and conversation history
    # Don't reset: session_id, conversation_turn, conversation_history, node_history
    
    return state