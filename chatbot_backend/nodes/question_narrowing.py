# nodes/case_narrowing.py

import logging
from typing import Dict, Any, List, Optional
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata
from services.azure_search import search_service

logger = logging.getLogger(__name__)

def case_narrowing_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    케이스 좁히기 노드 - 확정된 이슈 내에서 구체적인 케이스 결정
    
    프로세스:
    1. 현재 이슈 타입으로 필터링된 케이스들 검색
    2. 수집된 정보와 대화 맥락을 분석
    3. LLM으로 케이스 결정 가능 여부 판단
    4. 케이스 확정 또는 추가 질문 필요 판단
    
    Args:
        state: 현재 챗봇 상태
        config: 대화 설정 정보
        llm: Azure OpenAI LLM 인스턴스
        
    Returns:
        ChatbotState: 업데이트된 상태
    """
    
    # 메타데이터 업데이트
    state = update_state_metadata(state, "case_narrowing")
    
    logger.info(f"🎯 Case Narrowing - Issue: {state['current_issue']}")
    logger.info(f"   Gathered Info: {len(state['gathered_info'])} items")
    logger.info(f"   Questions Asked: {state['question_count']}")
    
    try:
        # 1. 현재 이슈 타입으로 필터링된 케이스들 검색
        filtered_cases = _search_cases_by_issue(state, config)
        
        if not filtered_cases:
            logger.warning("   ⚠️ No cases found for current issue")
            state['needs_escalation'] = True
            state['escalation_reason'] = "no_cases_found"
            state['final_response'] = config['fallback_responses']['escalation']
            return state
        
        # 2. 수집된 정보 컨텍스트 구성
        conversation_context = _build_conversation_context(state)
        
        # 3. LLM으로 케이스 결정 시도
        case_decision = _analyze_case_with_llm(
            state, 
            filtered_cases, 
            conversation_context, 
            config, 
            llm
        )
        
        # 4. 케이스 결정 결과 처리
        if case_decision['case_determined']:
            # 케이스 확정
            state['current_case'] = case_decision['case_id']
            state['solution_ready'] = True
            state['classification_confidence'] = case_decision['confidence']
            
            logger.info(f"   ✅ Case determined: {case_decision['case_id']} (confidence: {case_decision['confidence']:.2f})")
            
        elif case_decision['needs_question']:
            # 추가 질문 필요
            logger.info("   📝 Additional information needed")
            # Question Generator가 처리하도록 상태 설정
            state['solution_ready'] = False
            
        else:
            # 결정 불가 - 에스컬레이션
            logger.info("   ⚠️ Cannot determine case - escalating")
            state['needs_escalation'] = True
            state['escalation_reason'] = "case_undetermined"
            state['final_response'] = config['fallback_responses']['escalation']
        
    except Exception as e:
        logger.error(f"   ❌ Case narrowing error: {e}")
        state['error_count'] += 1
        
        if state['error_count'] < 3:
            state['final_response'] = config['fallback_responses']['general_error']
        else:
            state['needs_escalation'] = True
            state['escalation_reason'] = "too_many_errors"
            state['final_response'] = config['fallback_responses']['escalation']
    
    return state

def _search_cases_by_issue(state: ChatbotState, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    현재 이슈 타입으로 필터링된 케이스들 검색
    
    Args:
        state: 현재 챗봇 상태
        config: 설정 정보
        
    Returns:
        List[Dict]: 필터링된 케이스들
    """
    
    if not state['current_issue']:
        return []
    
    # 사용자 메시지와 수집된 정보를 결합한 검색 쿼리 구성
    search_query = state['user_message']
    
    # 수집된 답변들도 검색 쿼리에 추가
    if state['answers_received']:
        search_query += " " + " ".join(state['answers_received'][-2:])  # 최근 2개 답변만
    
    # 이슈 타입으로 필터링된 검색
    filtered_cases = search_service.filter_cases_by_issue_type(
        query=search_query,
        issue_type=state['current_issue'],
        top_k=5
    )
    
    logger.info(f"   🔍 Found {len(filtered_cases)} cases for issue '{state['current_issue']}'")
    return filtered_cases

def _build_conversation_context(state: ChatbotState) -> str:
    """
    대화 맥락 구성
    
    Args:
        state: 현재 챗봇 상태
        
    Returns:
        str: 대화 맥락 텍스트
    """
    
    context_parts = []
    
    # 초기 사용자 메시지
    context_parts.append(f"초기 문의: {state['user_message']}")
    
    # 수집된 정보
    if state['gathered_info']:
        context_parts.append("수집된 정보:")
        for key, info in state['gathered_info'].items():
            if isinstance(info, dict):
                context_parts.append(f"- {info.get('question', key)}: {info.get('answer', 'N/A')}")
            else:
                context_parts.append(f"- {key}: {info}")
    
    # 최근 대화 기록
    if state['conversation_history']:
        context_parts.append("최근 대화:")
        for turn in state['conversation_history'][-3:]:  # 최근 3턴만
            context_parts.append(f"- 사용자: {turn.get('user', '')}")
            if turn.get('bot'):
                context_parts.append(f"- 봇: {turn.get('bot', '')[:100]}...")
    
    return "\n".join(context_parts)

def _analyze_case_with_llm(
    state: ChatbotState,
    cases: List[Dict[str, Any]], 
    conversation_context: str,
    config: Dict[str, Any], 
    llm: AzureChatOpenAI
) -> Dict[str, Any]:
    """
    LLM을 사용한 케이스 분석 및 결정
    
    Args:
        state: 현재 챗봇 상태
        cases: 가능한 케이스들
        conversation_context: 대화 맥락
        config: 설정 정보
        llm: LLM 인스턴스
        
    Returns:
        Dict: 케이스 결정 결과
    """
    
    # 케이스 정보 구성
    case_descriptions = []
    for i, case in enumerate(cases, 1):
        case_info = f"""
케이스 {i}: {case.get('case_name', 'Unknown')} (ID: {case.get('case_type', case.get('id', ''))})
설명: {case.get('description', '')}
일반적인 증상: {', '.join(case.get('symptoms', [])[:3])}
확인이 필요한 정보: {', '.join(case.get('questions_to_ask', [])[:2])}
"""
        case_descriptions.append(case_info)
    
    # 프롬프트 구성
    prompt_template = config['conversation_flow']['case_narrowing']['prompt_template']
    confidence_threshold = config['conversation_flow']['case_narrowing']['confidence_threshold']
    
    full_prompt = f"""
{prompt_template.format(
    issue=state['current_issue'],
    user_message=state['user_message'],
    conversation_context=conversation_context
)}

가능한 케이스들:
{chr(10).join(case_descriptions)}

현재 수집된 정보를 바탕으로 다음 중 하나를 결정하세요:

1. 케이스가 충분히 명확하다면 (신뢰도 {confidence_threshold} 이상):
   결정: CASE_DETERMINED
   케이스ID: [가장 적합한 케이스의 ID]
   신뢰도: [0.0-1.0]
   이유: [결정 근거]

2. 더 많은 정보가 필요하다면:
   결정: NEED_MORE_INFO
   이유: [어떤 정보가 더 필요한지]
   
3. 케이스를 결정할 수 없다면:
   결정: UNDETERMINED
   이유: [결정할 수 없는 이유]

다음 형식으로 답변하세요:
결정: [CASE_DETERMINED/NEED_MORE_INFO/UNDETERMINED]
케이스ID: [해당하는 경우]
신뢰도: [해당하는 경우, 0.0-1.0]
이유: [상세한 설명]
"""
    
    try:
        response = llm.invoke(full_prompt)
        result = response.content.strip()
        
        # 응답 파싱
        decision = _parse_case_decision(result, confidence_threshold)
        
        logger.info(f"   🤖 LLM Decision: {decision['decision']}")
        if decision.get('case_id'):
            logger.info(f"   📋 Selected Case: {decision['case_id']}")
            
        return decision
        
    except Exception as e:
        logger.error(f"LLM case analysis error: {e}")
        return {
            'case_determined': False,
            'needs_question': True,
            'decision': 'ERROR',
            'confidence': 0.0
        }

def _parse_case_decision(response: str, confidence_threshold: float) -> Dict[str, Any]:
    """
    LLM 케이스 결정 응답 파싱
    
    Args:
        response: LLM 응답
        confidence_threshold: 신뢰도 임계값
        
    Returns:
        Dict: 파싱된 결정 결과
    """
    
    lines = response.split('\n')
    decision = None
    case_id = None
    confidence = 0.0
    reason = ""
    
    for line in lines:
        line = line.strip()
        if line.startswith('결정:'):
            decision = line.replace('결정:', '').strip()
        elif line.startswith('케이스ID:'):
            case_id = line.replace('케이스ID:', '').strip()
        elif line.startswith('신뢰도:'):
            try:
                confidence_str = line.replace('신뢰도:', '').strip()
                confidence = float(confidence_str)
            except ValueError:
                confidence = 0.0
        elif line.startswith('이유:'):
            reason = line.replace('이유:', '').strip()
    
    # 결정 결과 구성
    if decision == 'CASE_DETERMINED' and case_id and confidence >= confidence_threshold:
        return {
            'case_determined': True,
            'needs_question': False,
            'case_id': case_id,
            'confidence': confidence,
            'decision': decision,
            'reason': reason
        }
    elif decision == 'NEED_MORE_INFO':
        return {
            'case_determined': False,
            'needs_question': True,
            'decision': decision,
            'confidence': confidence,
            'reason': reason
        }
    else:
        return {
            'case_determined': False,
            'needs_question': False,
            'decision': decision or 'UNDETERMINED',
            'confidence': confidence,
            'reason': reason
        }

def get_next_action(state: ChatbotState) -> str:
    """
    Case Narrowing 후 다음 액션 결정
    LangGraph conditional_edges에서 사용
    
    Args:
        state: 현재 챗봇 상태
        
    Returns:
        str: 다음 노드 이름
    """
    
    if state['needs_escalation']:
        return "END"
    elif state['solution_ready']:
        return "solution_delivery"
    else:
        return "question_generation"