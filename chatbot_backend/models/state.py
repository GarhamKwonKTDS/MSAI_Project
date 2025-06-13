# chatbot_backend/models/states.py

from typing import Dict, List, Optional, TypedDict

class ChatbotState(TypedDict):
    """
    LangGraph chatbot state with only the fields we're using
    """
    
    # User input and conversation
    user_message: str
    conversation_history: List[Dict[str, str]]
    session_id: str
    conversation_turn: int
    
    # Issue/Case classification
    current_issue: Optional[str]
    current_case: Optional[str]
    classification_confidence: float
    case_confidence: float
    classification_attempts: int
    
    # Search and RAG
    retrieved_cases: List[Dict]
    matched_cases: List[Dict]
    rag_used: bool
    
    # Information gathering
    gathered_info: Dict[str, str]
    
    # Flags for state management
    flag: Optional[str]  # For non-error states: 'no_search_results', 'low_confidence', etc.
    error_flag: Optional[str]  # For errors: 'llm_error', 'json_parse_error', etc.
    
    # Response
    final_response: str
    
    # Metadata
    last_node: str
    node_history: List[str]
    last_activity_time: str

def create_initial_state(user_message: str, session_id: str) -> ChatbotState:
    """
    Create initial state for a new conversation
    
    Args:
        user_message: User's message
        session_id: Session identifier
        
    Returns:
        ChatbotState: Initial state
    """
    from datetime import datetime
    
    return ChatbotState(
        # User input and conversation
        user_message=user_message,
        conversation_history=[],
        session_id=session_id,
        conversation_turn=1,
        
        # Issue/Case classification
        current_issue=None,
        current_case=None,
        classification_confidence=0.0,
        case_confidence=0.0,
        classification_attempts=0,
        
        # Search and RAG
        retrieved_cases=[],
        matched_cases=[],
        rag_used=False,
        
        # Information gathering
        gathered_info={},
        
        # Flags
        flag=None,
        error_flag=None,
        
        # Response
        final_response="",
        
        # Metadata
        last_node="",
        node_history=[],
        last_activity_time=datetime.utcnow().isoformat()
    )

def update_state_metadata(state: ChatbotState, node_name: str) -> ChatbotState:
    """
    Update state metadata when entering a node
    
    Args:
        state: Current chatbot state
        node_name: Name of the current node
        
    Returns:
        ChatbotState: Updated state
    """
    state['last_node'] = node_name
    
    if 'node_history' not in state:
        state['node_history'] = []
    state['node_history'].append(node_name)
    
    state['last_activity_time'] = datetime.utcnow().isoformat()
    
    return state

# def add_conversation_turn(state: ChatbotState, user_input: str, bot_response: str) -> ChatbotState:
#     """
#     대화 기록에 새로운 턴을 추가하는 헬퍼 함수
    
#     Args:
#         state: 현재 챗봇 상태
#         user_input: 사용자 입력
#         bot_response: 봇 응답
        
#     Returns:
#         ChatbotState: 업데이트된 상태
#     """
#     state['conversation_history'].append({
#         'user': user_input,
#         'bot': bot_response,
#         'turn': state['conversation_turn'],
#         'timestamp': datetime.utcnow().isoformat()
#     })
    
#     state['conversation_turn'] += 1
#     return state

# def should_escalate(state: ChatbotState, config: Dict) -> bool:
#     """
#     에스컬레이션이 필요한지 판단하는 헬퍼 함수
    
#     Args:
#         state: 현재 챗봇 상태
#         config: 대화 설정
        
#     Returns:
#         bool: 에스컬레이션 필요 여부
#     """
#     # 최대 질문 수 도달
#     if state['question_count'] >= config['conversation_flow']['case_narrowing']['max_questions_per_case']:
#         state['escalation_reason'] = "max_questions_reached"
#         return True
    
#     # 최대 대화 턴 수 도달
#     if state['conversation_turn'] >= config['conversation_management']['max_conversation_turns']:
#         state['escalation_reason'] = "max_turns_reached"
#         return True
    
#     # 분류 실패 횟수 초과
#     if state['classification_attempts'] >= config['conversation_flow']['issue_classification']['max_classification_attempts']:
#         state['escalation_reason'] = "classification_failed"
#         return True
    
#     # 오류 발생 횟수 초과
#     if state['error_count'] >= config['conversation_management']['escalation_after_failed_attempts']:
#         state['escalation_reason'] = "too_many_errors"
#         return True
    
#     return False