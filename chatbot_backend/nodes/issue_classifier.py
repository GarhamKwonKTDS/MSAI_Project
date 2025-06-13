# nodes/issue_classifier.py

import logging
from typing import Dict, Any, List
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata
from services.azure_search import search_service

logger = logging.getLogger(__name__)

def issue_classification_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    이슈 분류 노드 - Azure Search를 사용하여 사용자 메시지를 이슈 카테고리로 분류
    
    프로세스:
    1. Azure Search로 관련 케이스들 검색
    2. 검색 결과를 기반으로 이슈 타입 추출
    3. LLM으로 이슈 분류 확인 및 신뢰도 평가
    4. 분류 결과를 상태에 저장
    
    Args:
        state: 현재 챗봇 상태
        config: 대화 설정 정보
        llm: Azure OpenAI LLM 인스턴스
        
    Returns:
        ChatbotState: 업데이트된 상태
    """
    
    # 메타데이터 업데이트
    state = update_state_metadata(state, "issue_classification")
    state['classification_attempts'] += 1
    
    logger.info(f"🏷️ Issue Classification - Attempt {state['classification_attempts']}")
    logger.info(f"   User Message: {state['user_message'][:100]}...")
    
    try:
        # 1. Azure Search로 관련 케이스 검색
        search_query = _build_search_query(state['user_message'])
        state['search_query'] = search_query
        
        retrieved_cases = search_service.search_cases(search_query, top_k=5)
        state['retrieved_cases'] = retrieved_cases
        
        if retrieved_cases:
            state['rag_used'] = True
            logger.info(f"   🔍 Found {len(retrieved_cases)} relevant cases")
            
            # 검색 결과에서 이슈 타입들 추출
            issue_types = _extract_issue_types_from_search(retrieved_cases)
            
            # RAG 컨텍스트 구성
            rag_context = search_service.build_rag_context(retrieved_cases)
            state['rag_context'] = rag_context
            
        else:
            logger.warning("   ⚠️ No relevant cases found in search")
            issue_types = []
            state['rag_used'] = False
        
        # 2. LLM을 사용한 이슈 분류
        classified_issue, confidence = _classify_with_llm(
            state['user_message'], 
            issue_types, 
            state.get('rag_context', ''),
            config, 
            llm
        )
        
        # 3. 분류 결과 검증 및 저장
        confidence_threshold = config['conversation_flow']['issue_classification']['confidence_threshold']
        
        if classified_issue and confidence >= confidence_threshold:
            state['current_issue'] = classified_issue
            state['classification_confidence'] = confidence
            logger.info(f"   ✅ Issue classified: {classified_issue} (confidence: {confidence:.2f})")
            
        else:
            state['classification_confidence'] = confidence
            logger.info(f"   ❓ Low confidence classification: {classified_issue} ({confidence:.2f})")
            
            # 신뢰도가 낮으면 명확화 질문 생성
            if state['classification_attempts'] < config['conversation_flow']['issue_classification']['max_classification_attempts']:
                clarification = _generate_clarification_question(state['user_message'], issue_types, config, llm)
                state['final_response'] = clarification
                logger.info("   📝 Generated clarification question")
            else:
                # 최대 시도 횟수 초과시 에스컬레이션
                state['needs_escalation'] = True
                state['escalation_reason'] = "classification_failed"
                state['final_response'] = config['fallback_responses']['classification_unclear']
                logger.info("   ⚠️ Max classification attempts reached - escalating")
        
    except Exception as e:
        logger.error(f"   ❌ Issue classification error: {e}")
        state['error_count'] += 1
        state['classification_confidence'] = 0.0
        
        if state['error_count'] < 3:
            state['final_response'] = config['fallback_responses']['general_error']
        else:
            state['needs_escalation'] = True
            state['escalation_reason'] = "too_many_errors"
            state['final_response'] = config['fallback_responses']['escalation']
    
    return state

def _build_search_query(user_message: str) -> str:
    """
    사용자 메시지에서 검색 쿼리 구성
    
    Args:
        user_message: 사용자 메시지
        
    Returns:
        str: 검색 쿼리
    """
    # 간단한 전처리 (향후 더 정교한 쿼리 구성 가능)
    query = user_message.strip()
    
    # 불필요한 문구 제거
    stop_phrases = ["안녕하세요", "도와주세요", "문제가 있어요", "문제가 생겼어요"]
    for phrase in stop_phrases:
        query = query.replace(phrase, "")
    
    return query.strip()

def _extract_issue_types_from_search(cases: List[Dict[str, Any]]) -> List[str]:
    """
    검색 결과에서 이슈 타입들 추출
    
    Args:
        cases: 검색된 케이스들
        
    Returns:
        List[str]: 고유한 이슈 타입들
    """
    issue_types = []
    for case in cases:
        issue_type = case.get('issue_type')
        if issue_type and issue_type not in issue_types:
            issue_types.append(issue_type)
    
    return issue_types

def _classify_with_llm(
    user_message: str, 
    issue_types: List[str], 
    rag_context: str,
    config: Dict[str, Any], 
    llm: AzureChatOpenAI
) -> tuple[str, float]:
    """
    LLM을 사용한 이슈 분류
    
    Args:
        user_message: 사용자 메시지
        issue_types: 가능한 이슈 타입들
        rag_context: RAG 컨텍스트
        config: 설정 정보
        llm: LLM 인스턴스
        
    Returns:
        tuple: (분류된 이슈, 신뢰도)
    """
    
    # 프롬프트 구성
    prompt_template = config['conversation_flow']['issue_classification']['prompt_template']
    
    if issue_types and rag_context:
        full_prompt = f"""
{prompt_template.format(user_message=user_message)}

검색된 관련 케이스 정보:
{rag_context}

가능한 이슈 타입들:
{', '.join(issue_types)}

다음 형식으로 답변하세요:
이슈타입: [가장 적합한 이슈 타입]
신뢰도: [0.0-1.0 사이의 숫자]
이유: [분류 근거]

확실하지 않으면 '불명확'이라고 답하세요.
"""
    else:
        full_prompt = f"""
{prompt_template.format(user_message=user_message)}

검색 결과가 없어 일반적인 분류를 시도합니다.

다음 형식으로 답변하세요:
이슈타입: [추정되는 이슈 타입 또는 '불명확']
신뢰도: [0.0-1.0 사이의 숫자]
이유: [분류 근거]
"""
    
    try:
        response = llm.invoke(full_prompt)
        result = response.content.strip()
        
        # 응답 파싱
        issue_type, confidence = _parse_classification_response(result)
        
        return issue_type, confidence
        
    except Exception as e:
        logger.error(f"LLM classification error: {e}")
        return None, 0.0

def _parse_classification_response(response: str) -> tuple[str, float]:
    """
    LLM 분류 응답 파싱
    
    Args:
        response: LLM 응답
        
    Returns:
        tuple: (이슈타입, 신뢰도)
    """
    
    lines = response.split('\n')
    issue_type = None
    confidence = 0.0
    
    for line in lines:
        line = line.strip()
        if line.startswith('이슈타입:'):
            issue_type = line.replace('이슈타입:', '').strip()
            if issue_type == '불명확':
                issue_type = None
        elif line.startswith('신뢰도:'):
            try:
                confidence_str = line.replace('신뢰도:', '').strip()
                confidence = float(confidence_str)
            except ValueError:
                confidence = 0.0
    
    return issue_type, confidence

def _generate_clarification_question(
    user_message: str, 
    issue_types: List[str], 
    config: Dict[str, Any], 
    llm: AzureChatOpenAI
) -> str:
    """
    명확화 질문 생성
    
    Args:
        user_message: 사용자 메시지
        issue_types: 가능한 이슈 타입들
        config: 설정 정보
        llm: LLM 인스턴스
        
    Returns:
        str: 명확화 질문
    """
    
    if not issue_types:
        return config['fallback_responses']['classification_unclear']
    
    prompt = f"""
사용자 메시지: "{user_message}"

가능한 문제 유형들: {', '.join(issue_types)}

사용자의 문제를 정확히 파악하기 위한 명확화 질문을 생성하세요.
- 친근하고 도움이 되는 톤으로
- 구체적이고 이해하기 쉽게
- 한 번에 하나의 질문만

질문:
"""
    
    try:
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.error(f"Clarification question generation error: {e}")
        return config['fallback_responses']['need_more_info']