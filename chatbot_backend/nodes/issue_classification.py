# nodes/issue_classification.py

import logging
import json
from typing import Dict, Any, List
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata

logger = logging.getLogger(__name__)

def issue_classification_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    Issue Classification Node - Classifies user message into issue categories
    
    Args:
        state: Current chatbot state
        config: Conversation configuration
        llm: Azure OpenAI LLM instance
        
    Returns:
        ChatbotState: Updated state
    """
    
    # Update metadata
    state = update_state_metadata(state, "issue_classification")
    state['classification_attempts'] += 1
    
    logger.info(f"🏷️ Issue Classification - Attempt {state['classification_attempts']}")
    logger.info(f"   User Message: {state['user_message'][:100]}...")
    
    # Search for relevant cases
    from services.azure_search import search_service
    
    retrieved_cases = search_service.search_cases(state['user_message'], top_k=5)
    state['retrieved_cases'] = retrieved_cases
    state['rag_used'] = len(retrieved_cases) > 0
    
    logger.info(f"   🔍 Found {len(retrieved_cases)} relevant cases")
    
    # Extract unique issue types from search results
    issue_types = _extract_issue_types(retrieved_cases)
    
    if issue_types:
        # Build RAG context for LLM
        rag_context = search_service.build_rag_context(retrieved_cases)
        logger.info(f"   📋 Extracted issue types: {issue_types}")
    else:
        logger.warning("   ⚠️ No issue types found in search results")
    
    ## Use LLM to classify the issue
    if issue_types:
        classification_result = _classify_with_llm(
            state['user_message'],
            issue_types,
            rag_context,
            config,
            llm
        )
        
        # Process classification result
        confidence_threshold = config['conversation_flow']['issue_classification']['confidence_threshold']
        
        if classification_result['issue_type'] and classification_result['confidence'] >= confidence_threshold:
            # Successful classification
            state['current_issue'] = classification_result['issue_type']
            state['classification_confidence'] = classification_result['confidence']
            logger.info(f"   ✅ Issue classified: {state['current_issue']} (confidence: {state['classification_confidence']:.2f})")
        else:
            # Low confidence - current_issue remains None
            state['flag'] = 'low_confidence'
            logger.info(f"   ❓ Low confidence: {classification_result.get('issue_type')} ({classification_result['confidence']:.2f})")
    else:
        # No search results - current_issue remains None
        state['flag'] = 'no_search_results'
        logger.info("   ❓ No search results for classification")
    
    return state

def determine_next_issue_classification(state: ChatbotState) -> str:
    """
    Determines next node after issue classification
    Used by LangGraph conditional_edges
    
    Args:
        state: Current chatbot state
        
    Returns:
        str: Name of next node
    """
    
    if state.get('current_issue'):
        # Issue successfully classified
        logger.info("   → Issue classified - routing to: case_narrowing")
        return "case_narrowing"
    else:
        # Issue not classified
        logger.info("   → Issue not classified - routing to: reply_formulation")
        return "reply_formulation"

def _extract_issue_types(cases: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique issue types from retrieved cases
    
    Args:
        cases: List of retrieved cases
        
    Returns:
        List[str]: Unique issue types
    """
    issue_types = []
    issue_names = {}  # Store issue_type -> issue_name mapping
    
    for case in cases:
        issue_type = case.get('issue_type')
        issue_name = case.get('issue_name')
        
        if issue_type and issue_type not in issue_types:
            issue_types.append(issue_type)
            if issue_name:
                issue_names[issue_type] = issue_name
    
    return issue_types

def _classify_with_llm(
    user_message: str,
    issue_types: List[str],
    rag_context: str,
    config: Dict[str, Any],
    llm: AzureChatOpenAI
    ) -> Dict[str, Any]:
    """
    Use LLM to classify the issue type
    
    Args:
        user_message: User's message
        issue_types: List of possible issue types from search
        rag_context: RAG context from search results
        config: Conversation configuration
        llm: LLM instance
        
    Returns:
        Dict with 'issue_type', 'confidence', and 'reason'
    """
    
    # Build context section based on what we have
    if rag_context and issue_types:
        context_section = f"""검색된 관련 케이스 정보:
    {rag_context}

    가능한 이슈 타입들: {', '.join(issue_types)}"""
    else:
        context_section = "검색 결과가 없어 일반적인 분류를 시도합니다."
    
    # Get prompt template from config
    prompt_template = config['conversation_flow']['issue_classification']['classification_prompt']
    
    # Build the full prompt
    prompt = prompt_template.format(
        user_message=user_message,
        context_section=context_section
    )

    # Append common JSON instruction
    prompt += "\n\n" + config['conversation_flow']['common']['json_parse_instruction']

    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content.strip())
        
        return {
            'issue_type': result.get('issue_type'),
            'confidence': float(result.get('confidence', 0.0)),
            'reason': result.get('reason', '')
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in issue classification: {e}")
        return {'issue_type': None, 'confidence': 0.0, 'reason': 'JSON parse error'}
    except Exception as e:
        logger.error(f"Issue classification error: {e}")
        return {'issue_type': None, 'confidence': 0.0, 'reason': str(e)}