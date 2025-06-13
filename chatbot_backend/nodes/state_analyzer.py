# nodes/state_analyzer.py

import logging
from typing import Dict, Any
from models.state import ChatbotState, update_state_metadata, check_escalation_conditions

logger = logging.getLogger(__name__)

def state_analyzer_node(state: ChatbotState, config: Dict[str, Any]) -> ChatbotState:
    """
    상태 분석 노드 - 현재 대화 상태를 분석하고 다음 노드를 결정
    
    라우팅 로직:
    1. 에스컬레이션 필요시 → END (종료)
    2. current_issue가 없으면 → issue_classification
    3. current_issue는 있지만 current_case가 없으면 → case_narrowing  
    4. 둘 다 있고 solution_ready가 True → solution_delivery
    5. 둘 다 있지만 solution_ready가 False → case_narrowing (재분석)
    
    Args:
        state: 현재 챗봇 상태
        config: 대화 설정 정보
        
    Returns:
        ChatbotState: 업데이트된 상태
    """
    
    # 메타데이터 업데이트
    state = update_state_metadata(state, "state_analyzer")
    
    logger.info(f"🔍 State Analyzer - Turn {state['conversation_turn']}")
    logger.info(f"   Session: {state['session_id']}")
    logger.info(f"   Issue: {state['current_issue']}")
    logger.info(f"   Case: {state['current_case']}")
    logger.info(f"   Solution Ready: {state['solution_ready']}")
    logger.info(f"   Questions Asked: {state['question_count']}")
    
    # 에스컬레이션 조건 체크
    state = check_escalation_conditions(state, config)
    
    # 1. 에스컬레이션이 필요한 경우
    if state['needs_escalation']:
        logger.info(f"   → ESCALATION: {state['escalation_reason']}")
        
        # 에스컬레이션 응답 설정
        escalation_reason = state['escalation_reason']
        if escalation_reason == "max_turns_reached":
            state['final_response'] = config['fallback_responses']['max_turns_reached']
        elif escalation_reason == "max_questions_exceeded":
            state['final_response'] = config['fallback_responses']['escalation']
        elif escalation_reason == "classification_failed":
            state['final_response'] = config['fallback_responses']['classification_unclear']
        else:
            state['final_response'] = config['fallback_responses']['escalation']
        
        state['last_node'] = "escalation"
        return state
    
    # 2. 세션 타임아웃 체크 (실제 구현에서는 시간 기반 체크 필요)
    if state['session_timeout']:
        logger.info("   → SESSION TIMEOUT")
        state['final_response'] = config['fallback_responses']['session_timeout']
        state['last_node'] = "timeout"
        return state
    
    # 3. 이슈가 분류되지 않은 경우
    if not state['current_issue']:
        logger.info("   → Issue Classification (이슈 미분류)")
        state['last_node'] = "issue_classification"
        return state
    
    # 4. 이슈는 있지만 케이스가 없는 경우
    if not state['current_case']:
        logger.info("   → Case Narrowing (케이스 미확정)")
        state['last_node'] = "case_narrowing"
        return state
    
    # 5. 이슈와 케이스가 모두 있지만 솔루션이 준비되지 않은 경우
    if not state['solution_ready']:
        logger.info("   → Case Narrowing (솔루션 미준비 - 재분석)")
        state['last_node'] = "case_narrowing"
        return state
    
    # 6. 모든 조건이 충족된 경우 - 솔루션 제공
    logger.info("   → Solution Delivery (모든 조건 충족)")
    state['last_node'] = "solution_delivery"
    return state

def determine_next_node(state: ChatbotState) -> str:
    """
    State Analyzer 결과를 바탕으로 다음 노드 결정
    LangGraph의 conditional_edges에서 사용
    
    Args:
        state: 현재 챗봇 상태
        
    Returns:
        str: 다음에 실행할 노드 이름
    """
    
    # 에스컬레이션이나 타임아웃인 경우 종료
    if state['needs_escalation'] or state['session_timeout']:
        return "END"
    
    # last_node에 저장된 다음 노드 반환
    next_node = state.get('last_node', 'issue_classification')
    
    logger.info(f"🎯 Next Node: {next_node}")
    return next_node

def log_state_summary(state: ChatbotState) -> None:
    """
    디버깅을 위한 상태 요약 로깅
    
    Args:
        state: 현재 챗봇 상태
    """
    
    logger.debug("=" * 50)
    logger.debug("STATE SUMMARY")
    logger.debug(f"Session: {state['session_id']}")
    logger.debug(f"Turn: {state['conversation_turn']}")
    logger.debug(f"User Message: {state['user_message'][:100]}...")
    logger.debug(f"Current Issue: {state['current_issue']}")
    logger.debug(f"Current Case: {state['current_case']}")
    logger.debug(f"Classification Confidence: {state['classification_confidence']}")
    logger.debug(f"Questions Asked: {state['question_count']}")
    logger.debug(f"Solution Ready: {state['solution_ready']}")
    logger.debug(f"Needs Escalation: {state['needs_escalation']}")
    logger.debug(f"Node History: {' → '.join(state['node_history'][-5:])}")
    logger.debug("=" * 50)