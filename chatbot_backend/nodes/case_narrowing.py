# nodes/case_narrowing.py

import logging
import json
from typing import Dict, Any, List
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata

logger = logging.getLogger(__name__)

def case_narrowing_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    Case Narrowing Node - Narrows down to specific case within identified issue
    
    Args:
        state: Current chatbot state
        config: Conversation configuration
        llm: Azure OpenAI LLM instance
        
    Returns:
        ChatbotState: Updated state
    """
    
   # Update metadata
    state = update_state_metadata(state, "case_narrowing")
    
    logger.info(f"🎯 Case Narrowing")
    logger.info(f"   Current Issue: {state['current_issue']}")
    logger.info(f"   User Message: {state['user_message'][:100]}...")
    
    # Generate optimized search query using LLM
    search_query = _generate_search_query(state, config, llm)
    logger.info(f"   🔍 Generated search query: {search_query}")
    
    # Search for cases within the current issue
    from services.azure_search import search_service
    
    try:
        filtered_cases = search_service.filter_cases_by_issue_type(
            query=search_query,
            issue_type=state['current_issue'],
            top_k=5
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        state['error_flag'] = 'search_error'  # ADD THIS
        return state
    
    logger.info(f"   📋 Found {len(filtered_cases)} cases for issue '{state['current_issue']}'")

    # Step 3: Use LLM to match cases
    if filtered_cases:
        matched_cases = _match_cases_with_llm(state, filtered_cases, config, llm)
        
        if len(matched_cases) == 0:
            logger.info("   ❌ No cases matched")
            
        elif len(matched_cases) == 1:
            logger.info(f"   ✅ Single case matched: {matched_cases[0]['case_id']}")
            state['current_case'] = matched_cases[0]['case_id']
            state['case_confidence'] = matched_cases[0]['confidence']
            
        else:  # 2+ matches
            logger.info(f"   ⚠️ Multiple cases matched: {len(matched_cases)}")
            state['matched_cases'] = matched_cases
            
    else:
        logger.info("   ❌ No cases found in search")
    
    return state

def determine_next_case_narrowing(state: ChatbotState) -> str:
    """
    Determines next node after case narrowing
    Used by LangGraph conditional_edges
    
    Args:
        state: Current chatbot state
        
    Returns:
        str: Name of next node
    """
    
    # Always go to reply formulation
    logger.info("   → Routing to: reply_formulation")
    return "reply_formulation"

def _generate_search_query(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> str:
    """
    Generate an optimized search query from conversation context
    """
    
    # Build conversation context
    context_parts = [f"사용자의 초기 문제: {state['user_message']}"]
    
    if state.get('gathered_info'):
        for info in state['gathered_info'].values():
            if isinstance(info, dict) and info.get('answer'):
                context_parts.append(f"추가 정보: {info['answer']}")
    
    prompt = config['conversation_flow']['case_narrowing']['search_query_prompt'].format(
        context=chr(10).join(context_parts)
    )

    # Append common JSON instruction
    prompt += "\n\n" + config['conversation_flow']['common']['json_parse_instruction']

    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content.strip())
        return result.get('search_query', state['user_message'])
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in search query generation: {e}")
        state['error_flag'] = 'json_parse_error'  # ADD THIS
        return state['user_message']
    except Exception as e:
        logger.error(f"Search query generation error: {e}")
        state['error_flag'] = 'llm_error'  # ADD THIS
        return state['user_message']


def _match_cases_with_llm(
    state: ChatbotState, 
    cases: List[Dict[str, Any]], 
    config: Dict[str, Any], 
    llm: AzureChatOpenAI
) -> List[Dict[str, Any]]:
    """
    Use LLM to match user situation with cases
    """
    
    # Build case descriptions
    case_descriptions = []
    for i, case in enumerate(cases):
        case_descriptions.append(f"""
케이스 {i+1}: {case.get('case_name')} (ID: {case.get('case_type', case.get('id'))})
설명: {case.get('description')}
증상: {', '.join(case.get('symptoms', [])[:3])}""")
    
    prompt = config['conversation_flow']['case_narrowing']['case_matching_prompt'].format(
        user_message=state['user_message'],
        current_issue=state['current_issue'],
        case_descriptions=chr(10).join(case_descriptions)
    )

    # Append common JSON instruction
    prompt += "\n\n" + config['conversation_flow']['common']['json_parse_instruction']

    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content.strip())
        
        matched = []
        for match in result.get('matched_cases', []):
            case_num = match.get('case_number', 0) - 1
            if 0 <= case_num < len(cases):
                matched.append({
                    'case_id': match.get('case_id'),
                    'case_details': cases[case_num],
                    'confidence': match.get('confidence', 0.0),
                    'reason': match.get('reason', '')
                })
        
        return matched
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in case matching: {e}")
        state['error_flag'] = 'json_parse_error'  # ADD THIS
        return []
    except Exception as e:
        logger.error(f"Case matching error: {e}")
        state['error_flag'] = 'llm_error'  # ADD THIS
        return []