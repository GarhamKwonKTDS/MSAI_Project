# nodes/solution_delivery.py

import logging
from typing import Dict, Any, Optional
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata
from services.azure_search import search_service

logger = logging.getLogger(__name__)

def solution_delivery_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    솔루션 제공 노드 - 확정된 케이스에 대한 개인화된 해결책 생성 및 제공
    
    프로세스:
    1. 확정된 케이스의 상세 정보 조회
    2. 수집된 정보와 대화 맥락 분석
    3. 개인화된 솔루션 생성
    4. 후속 조치 및 에스컬레이션 옵션 포함
    
    Args:
        state: 현재 챗봇 상태
        config: 대화 설정 정보
        llm: Azure OpenAI LLM 인스턴스
        
    Returns:
        ChatbotState: 업데이트된 상태
    """
    
    # 메타데이터 업데이트
    state = update_state_metadata(state, "solution_delivery")
    
    logger.info(f"🎯 Solution Delivery")
    logger.info(f"   Issue: {state['current_issue']}")
    logger.info(f"   Case: {state['current_case']}")
    logger.info(f"   Gathered Info: {len(state['gathered_info'])} items")
    
    try:
        # 1. 케이스 상세 정보 조회
        case_details = _get_case_details(state)
        
        if not case_details:
            logger.error("   ❌ Could not retrieve case details")
            state['needs_escalation'] = True
            state['escalation_reason'] = "case_details_not_found"
            state['final_response'] = config['fallback_responses']['escalation']
            return state
        
        # 2. 개인화된 솔루션 생성
        solution = _generate_personalized_solution(
            state, 
            case_details, 
            config, 
            llm
        )
        
        if solution:
            # 3. 후속 조치 및 추가 옵션 포함
            final_response = _format_final_response(
                solution, 
                case_details, 
                state, 
                config
            )
            
            state['final_response'] = final_response
            state['resolution_attempted'] = True
            
            logger.info(f"   ✅ Solution delivered ({len(final_response)} chars)")
            
        else:
            logger.error("   ❌ Failed to generate solution")
            state['needs_escalation'] = True
            state['escalation_reason'] = "solution_generation_failed"
            state['final_response'] = config['fallback_responses']['escalation']
        
    except Exception as e:
        logger.error(f"   ❌ Solution delivery error: {e}")
        state['error_count'] += 1
        state['needs_escalation'] = True
        state['escalation_reason'] = "solution_delivery_error"
        state['final_response'] = config['fallback_responses']['general_error']
    
    return state

def _get_case_details(state: ChatbotState) -> Optional[Dict[str, Any]]:
    """
    확정된 케이스의 상세 정보 조회
    
    Args:
        state: 현재 챗봇 상태
        
    Returns:
        Optional[Dict]: 케이스 상세 정보
    """
    
    if not state['current_case']:
        return None
    
    # 1. 먼저 이미 검색된 케이스들에서 찾기
    for case in state.get('retrieved_cases', []):
        case_id = case.get('case_type') or case.get('id')
        if case_id == state['current_case']:
            logger.info(f"   📋 Found case details in retrieved cases")
            return case
    
    # 2. Azure Search에서 직접 조회
    try:
        case_details = search_service.get_case_by_id(state['current_case'])
        if case_details:
            logger.info(f"   📋 Retrieved case details from search")
            return case_details
    except Exception as e:
        logger.error(f"Error retrieving case details: {e}")
    
    # 3. 이슈 타입으로 필터링해서 다시 찾기
    if state['current_issue']:
        cases = search_service.filter_cases_by_issue_type(
            query=state['user_message'],
            issue_type=state['current_issue'],
            top_k=10
        )
        
        for case in cases:
            case_id = case.get('case_type') or case.get('id')
            if case_id == state['current_case']:
                logger.info(f"   📋 Found case details by filtering")
                return case
    
    logger.warning(f"   ⚠️ Could not find details for case: {state['current_case']}")
    return None

def _generate_personalized_solution(
    state: ChatbotState, 
    case_details: Dict[str, Any], 
    config: Dict[str, Any], 
    llm: AzureChatOpenAI
) -> Optional[str]:
    """
    개인화된 솔루션 생성
    
    Args:
        state: 현재 챗봇 상태
        case_details: 케이스 상세 정보
        config: 설정 정보
        llm: LLM 인스턴스
        
    Returns:
        Optional[str]: 생성된 솔루션
    """
    
    # 사용자 상황 정보 구성
    user_context = _build_user_context(state)
    
    # 케이스 해결 단계 정보
    solution_steps = case_details.get('solution_steps', [])
    escalation_triggers = case_details.get('escalation_triggers', [])
    
    # 프롬프트 구성
    prompt_template = config['conversation_flow']['solution_delivery']['prompt_template']
    
    full_prompt = f"""
{prompt_template.format(
    case=case_details.get('case_name', state['current_case']),
    gathered_info=user_context
)}

케이스 정보:
- 이름: {case_details.get('case_name', '')}
- 설명: {case_details.get('description', '')}

표준 해결 단계:
{chr(10).join([f"{i}. {step}" for i, step in enumerate(solution_steps, 1)])}

에스컬레이션 상황:
- {chr(10).join(escalation_triggers)}

응답 요구사항:
- 톤: {config['response_formatting']['tone']}
- 언어 스타일: {config['response_formatting']['language_style']}
- 최대 길이: {config['response_formatting']['max_response_length']}자
- 단계 번호 포함: {config['response_formatting']['include_step_numbers']}
- 설명 포함: {config['response_formatting']['include_explanations']}

사용자의 구체적인 상황을 고려하여 개인화된 해결 방법을 제시하세요.
각 단계에 대해 왜 그 단계가 필요한지 간단히 설명하고,
사용자가 실제로 따라할 수 있는 구체적인 지시사항을 제공하세요.
"""
    
    try:
        response = llm.invoke(full_prompt)
        solution = response.content.strip()
        
        # 길이 제한 체크
        max_length = config['response_formatting']['max_response_length']
        if len(solution) > max_length:
            # 길이가 초과하면 요약 버전 생성
            solution = _summarize_solution(solution, max_length, llm)
        
        return solution
        
    except Exception as e:
        logger.error(f"Solution generation error: {e}")
        return None

def _build_user_context(state: ChatbotState) -> str:
    """
    사용자 상황 컨텍스트 구성
    
    Args:
        state: 현재 챗봇 상태
        
    Returns:
        str: 사용자 상황 컨텍스트
    """
    
    context_parts = []
    
    # 초기 문제 상황
    context_parts.append(f"초기 문의: {state['user_message']}")
    
    # 수집된 구체적인 정보
    if state['gathered_info']:
        context_parts.append("\n사용자 상황:")
        for key, info in state['gathered_info'].items():
            if isinstance(info, dict):
                question = info.get('question', '')
                answer = info.get('answer', '')
                if question and answer:
                    context_parts.append(f"- {question}: {answer}")
            else:
                context_parts.append(f"- {key}: {info}")
    
    # 대화 중 언급된 추가 정보
    if state['conversation_history']:
        recent_context = []
        for turn in state['conversation_history'][-2:]:  # 최근 2턴
            user_msg = turn.get('user', '')
            if user_msg and user_msg != state['user_message']:
                recent_context.append(user_msg)
        
        if recent_context:
            context_parts.append(f"\n추가 언급사항: {' / '.join(recent_context)}")
    
    return "\n".join(context_parts)

def _format_final_response(
    solution: str, 
    case_details: Dict[str, Any], 
    state: ChatbotState, 
    config: Dict[str, Any]
) -> str:
    """
    최종 응답 포맷팅 (후속 조치 및 에스컬레이션 옵션 포함)
    
    Args:
        solution: 생성된 솔루션
        case_details: 케이스 상세 정보
        state: 현재 챗봇 상태
        config: 설정 정보
        
    Returns:
        str: 포맷팅된 최종 응답
    """
    
    response_parts = [solution]
    
    # 후속 조치 전략 추가
    if config['conversation_flow']['solution_delivery']['follow_up_strategy']:
        follow_up = config['conversation_flow']['solution_delivery']['follow_up_strategy']
        response_parts.append(f"\n\n{follow_up}")
    
    # 에스컬레이션 옵션 포함
    if config['conversation_flow']['solution_delivery']['include_escalation_option']:
        escalation_triggers = case_details.get('escalation_triggers', [])
        if escalation_triggers:
            response_parts.append("\n\n🚨 다음과 같은 경우 추가 지원이 필요합니다:")
            for trigger in escalation_triggers[:2]:  # 최대 2개만
                response_parts.append(f"- {trigger}")
            response_parts.append("\n이런 상황이 발생하면 전문 상담원에게 연결해드리겠습니다.")
    
    # 추가 도움 안내
    response_parts.append("\n\n💡 추가 질문이나 다른 문제가 있으시면 언제든 말씀해 주세요!")
    
    return "".join(response_parts)

def _summarize_solution(solution: str, max_length: int, llm: AzureChatOpenAI) -> str:
    """
    솔루션 요약 (길이 초과시)
    
    Args:
        solution: 원본 솔루션
        max_length: 최대 길이
        llm: LLM 인스턴스
        
    Returns:
        str: 요약된 솔루션
    """
    
    prompt = f"""
다음 해결 방법이 너무 길어서 {max_length}자 이내로 요약해야 합니다.
핵심 단계와 중요한 정보만 포함하여 간결하게 정리해주세요.

원본:
{solution}

요약 ({max_length}자 이내):
"""
    
    try:
        response = llm.invoke(prompt)
        summarized = response.content.strip()
        
        # 여전히 길면 강제로 자르기
        if len(summarized) > max_length:
            summarized = summarized[:max_length-3] + "..."
        
        return summarized
        
    except Exception as e:
        logger.error(f"Solution summarization error: {e}")
        # 실패시 원본을 강제로 자르기
        return solution[:max_length-3] + "..."