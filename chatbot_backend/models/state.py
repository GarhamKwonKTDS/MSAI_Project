# models/state.py
from typing import Dict, List, Optional, TypedDict
from datetime import datetime

class ChatbotState(TypedDict):
    """
    LangGraph용 챗봇 상태 관리 클래스
    Azure Search와 통합된 VoC 지원 시스템용
    """
    
    # === 사용자 입력 및 대화 관리 ===
    user_message: str
    conversation_history: List[Dict[str, str]]
    session_id: str
    conversation_turn: int
    
    # === Issue/Case 분류 및 관리 ===
    current_issue: Optional[str]
    current_case: Optional[str]
    classification_confidence: float
    classification_attempts: int
    
    # === Azure Search RAG 데이터 ===
    retrieved_cases: List[Dict]
    rag_context: str
    rag_used: bool
    search_queries: List[str]
    
    # === 정보 수집 및 질문 관리 ===
    gathered_info: Dict[str, str]
    questions_asked: List[str]
    question_count: int
    pending_question: Optional[str]
    
    # === 솔루션 및 상태 관리 ===
    solution_ready: bool
    final_response: str
    needs_escalation: bool
    escalation_reason: Optional[str]
    
    # === 메타데이터 및 추적 ===
    last_node: str
    node_history: List[str]
    error_count: int
    session_start_time: str
    last_activity_time: str
    
    # === 설정 및 플래그 ===
    max_questions_reached: bool
    conversation_timeout: bool
    debug_mode: bool

def create_initial_state(user_message: str, session_id: str, debug_mode: bool = False) -> ChatbotState:
    """
    초기 챗봇 상태를 생성하는 팩토리 함수
    
    Args:
        user_message: 사용자의 초기 메시지
        session_id: 세션 식별자
        debug_mode: 디버그 모드 활성화 여부
        
    Returns:
        ChatbotState: 초기화된 챗봇 상태
    """
    current_time = datetime.utcnow().isoformat()
    
    return ChatbotState(
        # 사용자 입력 및 대화
        user_message=user_message,
        conversation_history=[],
        session_id=session_id,
        conversation_turn=1,
        
        # Issue/Case 분류
        current_issue=None,
        current_case=None,
        classification_confidence=0.0,
        classification_attempts=0,
        
        # Azure Search RAG
        retrieved_cases=[],
        rag_context="",
        rag_used=False,
        search_queries=[],
        
        # 정보 수집
        gathered_info={},
        questions_asked=[],
        question_count=0,
        pending_question=None,
        
        # 솔루션 및 상태
        solution_ready=False,
        final_response="",
        needs_escalation=False,
        escalation_reason=None,
        
        # 메타데이터
        last_node="",
        node_history=[],
        error_count=0,
        session_start_time=current_time,
        last_activity_time=current_time,
        
        # 설정 및 플래그
        max_questions_reached=False,
        conversation_timeout=False,
        debug_mode=debug_mode
    )

def update_state_metadata(state: ChatbotState, node_name: str) -> ChatbotState:
    """
    상태의 메타데이터를 업데이트하는 헬퍼 함수
    
    Args:
        state: 현재 챗봇 상태
        node_name: 현재 실행 중인 노드 이름
        
    Returns:
        ChatbotState: 업데이트된 상태
    """
    state['last_node'] = node_name
    state['node_history'].append(node_name)
    state['last_activity_time'] = datetime.utcnow().isoformat()
    
    return state

def add_conversation_turn(state: ChatbotState, user_input: str, bot_response: str) -> ChatbotState:
    """
    대화 기록에 새로운 턴을 추가하는 헬퍼 함수
    
    Args:
        state: 현재 챗봇 상태
        user_input: 사용자 입력
        bot_response: 봇 응답
        
    Returns:
        ChatbotState: 업데이트된 상태
    """
    state['conversation_history'].append({
        'user': user_input,
        'bot': bot_response,
        'turn': state['conversation_turn'],
        'timestamp': datetime.utcnow().isoformat()
    })
    
    state['conversation_turn'] += 1
    return state

def should_escalate(state: ChatbotState, config: Dict) -> bool:
    """
    에스컬레이션이 필요한지 판단하는 헬퍼 함수
    
    Args:
        state: 현재 챗봇 상태
        config: 대화 설정
        
    Returns:
        bool: 에스컬레이션 필요 여부
    """
    # 최대 질문 수 도달
    if state['question_count'] >= config['conversation_flow']['case_narrowing']['max_questions_per_case']:
        state['escalation_reason'] = "max_questions_reached"
        return True
    
    # 최대 대화 턴 수 도달
    if state['conversation_turn'] >= config['conversation_management']['max_conversation_turns']:
        state['escalation_reason'] = "max_turns_reached"
        return True
    
    # 분류 실패 횟수 초과
    if state['classification_attempts'] >= config['conversation_flow']['issue_classification']['max_classification_attempts']:
        state['escalation_reason'] = "classification_failed"
        return True
    
    # 오류 발생 횟수 초과
    if state['error_count'] >= config['conversation_management']['escalation_after_failed_attempts']:
        state['escalation_reason'] = "too_many_errors"
        return True
    
    return False