# nodes/reply_formulation.py

import logging
import json
from typing import List, Dict, Any
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata

logger = logging.getLogger(__name__)

def reply_formulation_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    Reply Formulation Node - Generates appropriate responses based on current state
    
    This is the final node that creates user-facing messages based on what
    happened in previous nodes.
    
    Args:
        state: Current chatbot state
        config: Conversation configuration
        llm: Azure OpenAI LLM instance
        
    Returns:
        ChatbotState: Updated state with final_response
    """
    
    # Update metadata
    state = update_state_metadata(state, "reply_formulation")
    
    logger.info(f"📝 Reply Formulation")
    logger.info(f"   Previous Node: {state.get('node_history', [])[-2] if len(state.get('node_history', [])) > 1 else 'None'}")
    
    # Check for error flags first
    error_flag = state.get('error_flag')
    if error_flag:
        logger.info(f"   ❌ Error flag detected: {error_flag}")
        
        error_response_map = {
            'llm_error': 'llm_error',
            'search_error': 'search_error',
            'json_parse_error': 'json_parse_error',
            'timeout_error': 'timeout_error',
            'max_attempts_exceeded': 'max_attempts_exceeded'
        }
        
        response_key = error_response_map.get(error_flag, 'general_error')
        state['final_response'] = config['fallback_responses'][response_key]
        return state
    
    # Case 1: No issue identified
    if not state.get('current_issue'):
        logger.info("   Case: No issue identified")
        
        flag = state.get('flag')
        
        flag_response_map = {
            'no_search_results': 'no_search_results',
            'low_confidence': 'classification_unclear',
            'classification_failed': 'classification_unclear'
        }
        
        response_key = flag_response_map.get(flag, 'classification_unclear')
        state['final_response'] = config['fallback_responses'][response_key]
        
        logger.info(f"   Response type: {flag or 'default_clarification'}")
        return state
    
    # Case 2: Issue identified but no case determined
    if state.get('current_issue') and not state.get('current_case'):
        logger.info("   Case: Issue identified, no case determined")
        
        matched_cases = state.get('matched_cases', [])
        
        if len(matched_cases) == 0:
            # No matching cases found
            logger.info("   No matching cases")
            state['final_response'] = config['fallback_responses']['no_matching_cases']
            
        elif len(matched_cases) > 1:
            # Multiple cases matched - need disambiguation
            logger.info(f"   Multiple cases matched: {len(matched_cases)}")
            state['final_response'] = _generate_disambiguation_question(state, matched_cases, config, llm)
            
        else:
            # This shouldn't happen (single match should set current_case)
            logger.warning("   Unexpected state: single match but no current_case")
            state['final_response'] = config['fallback_responses']['general_error']
        
        return state
    
    # Case 3: Both issue and case identified - deliver solution
    if state.get('current_issue') and state.get('current_case'):
        logger.info("   Case: Issue and case identified - delivering solution")
        
        # Find the case details from matched_cases
        case_details = None
        for matched_case in state.get('matched_cases', []):
            if matched_case['case_id'] == state['current_case']:
                case_details = matched_case['case_details']
                break

        if case_details:
            state['final_response'] = _generate_solution_response(state, case_details, config, llm)
        else:
            # Fallback if case details not found
            logger.error("   Case details not found in matched_cases")
            state['final_response'] = config['fallback_responses']['general_error']
        
        return state
    
    # Fallback - this shouldn't happen
    logger.error("   Unexpected state - no matching condition")
    state['final_response'] = config['fallback_responses']['general_error']
    return state

def _generate_disambiguation_question(state: ChatbotState, matched_cases: List[Dict], config: Dict[str, Any], llm: AzureChatOpenAI) -> str:
    """
    Generate question to disambiguate between multiple matched cases
    """
    
    try:
        # Build case descriptions
        case_descriptions = []
        for i, case in enumerate(matched_cases[:3], 1):  # Limit to top 3
            case_details = case['case_details']
            case_descriptions.append(
                f"케이스 {i}: {case_details.get('case_name')}\n"
                f"   - 주요 증상: {', '.join(case_details.get('symptoms', [])[:2])}"
            )

        prompt = config['conversation_flow']['reply_formulation']['disambiguation_prompt'].format(
            user_message=state['user_message'],
            case_descriptions='\n'.join(case_descriptions)
        )

        # Append common JSON instruction
        prompt += "\n\n" + config['conversation_flow']['common']['json_parse_instruction']

        response = llm.invoke(prompt)
        result = json.loads(response.content.strip())
        return result.get('question', config['fallback_responses']['need_more_info'])
    except Exception as e:
        logger.error(f"Disambiguation question generation error: {e}")
        # Fallback to simple question
        case_names = [case['case_details']['case_name'] for case in matched_cases[:3]]
        return f"다음 중 어떤 상황에 가장 가까운가요? {', '.join(case_names)}"


def _generate_solution_response(state: ChatbotState, case_details: Dict[str, Any], config: Dict[str, Any], llm: AzureChatOpenAI) -> str:
    """
    Generate personalized solution response based on case details
    """

    try:
        # Prepare prompt
        case_name = case_details.get('case_name', '')
        solution_steps = case_details.get('solution_steps', [])
        
        prompt = config['conversation_flow']['reply_formulation']['solution_generation_prompt'].format(
            case_name=case_name,
            user_message=state['user_message'],
            solution_steps=chr(10).join([f"{i+1}. {step}" for i, step in enumerate(solution_steps)])
        )

        # Append common JSON instruction
        prompt += "\n\n" + config['conversation_flow']['common']['json_parse_instruction']

        response = llm.invoke(prompt)
        result = json.loads(response.content.strip())

        logger.info(f"Generated solution response: {result.get('response', '')[:100]}...")

        return result.get('response', config['fallback_responses']['general_error'])
    except Exception as e:
        logger.error(f"Solution generation error: {e}")
        # Fallback to showing standard solution steps
        return f"{case_name} 문제 해결 방법:\n\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(solution_steps)])