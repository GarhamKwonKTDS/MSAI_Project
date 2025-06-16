# utils/helpers.py

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def load_conversation_config(config_path: str = "configs/conversation_config.json") -> Dict[str, Any]:
    """
    대화 설정 파일 로딩
    
    Args:
        config_path: 설정 파일 경로
        
    Returns:
        Dict[str, Any]: 로딩된 설정
    """
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logger.info(f"✅ Loaded conversation config from {config_path}")
        return config
        
    except FileNotFoundError:
        logger.error(f"❌ Config file not found: {config_path}")
        return get_default_config()
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing error in {config_path}: {e}")
        return get_default_config()
    except Exception as e:
        logger.error(f"❌ Error loading config: {e}")
        return get_default_config()

def get_default_config() -> Dict[str, Any]:
    """
    기본 설정 반환 (fallback)
    
    Returns:
        Dict[str, Any]: 기본 설정
    """
    
    return {
        "conversation_flow": {
            "issue_classification": {
                "prompt_template": "사용자 메시지를 분석하여 문제 유형을 분류하세요: {user_message}",
                "confidence_threshold": 0.7,
                "fallback_action": "명확화_질문하기",
                "max_classification_attempts": 2
            },
            "case_narrowing": {
                "prompt_template": "문제 '{issue}'에 대한 구체적인 케이스를 결정하세요: {user_message}",
                "information_gathering_strategy": "점진적으로 정보를 수집하세요",
                "confidence_threshold": 0.8,
                "max_questions_per_case": 4,
                "question_selection_strategy": "progressive"
            },
            "solution_delivery": {
                "prompt_template": "케이스 '{case}'에 대한 해결책을 제공하세요: {gathered_info}",
                "personalization": True,
                "follow_up_strategy": "해결되었는지 확인하고 추가 도움을 제공하세요",
                "include_escalation_option": True
            }
        },
        "response_formatting": {
            "tone": "친근하고 전문적",
            "language_style": "존댓말",
            "max_response_length": 500,
            "include_step_numbers": True,
            "include_explanations": True
        },
        "conversation_management": {
            "session_timeout_minutes": 30,
            "max_conversation_turns": 20,
            "context_retention_turns": 10,
            "escalation_after_failed_attempts": 3
        },
        "fallback_responses": {
            "classification_unclear": "문제를 좀 더 구체적으로 설명해 주실 수 있나요?",
            "need_more_info": "더 자세한 정보가 필요합니다.",
            "escalation": "전문 상담원에게 연결해드리겠습니다.",
            "general_error": "처리 중 오류가 발생했습니다. 다시 시도해주세요.",
            "session_timeout": "세션이 만료되었습니다. 새로운 질문을 시작해주세요.",
            "max_turns_reached": "대화가 길어졌습니다. 전문 상담원에게 연결해드리겠습니다."
        },
        "logging_and_analytics": {
            "track_conversation_flow": True,
            "track_classification_accuracy": True,
            "track_resolution_success": True,
            "track_escalation_reasons": True
        }
    }

def validate_config(config: Dict[str, Any]) -> bool:
    """
    설정 유효성 검사
    
    Args:
        config: 검사할 설정
        
    Returns:
        bool: 유효성 검사 결과
    """
    
    try:
        # 필수 섹션 체크
        required_sections = [
            "conversation_flow",
            "response_formatting", 
            "conversation_management",
            "fallback_responses"
        ]
        
        for section in required_sections:
            if section not in config:
                logger.error(f"Missing required config section: {section}")
                return False
        
        # conversation_flow 하위 섹션 체크
        required_flow_sections = [
            "state_analysis",
            "issue_classification",
            "case_narrowing",
            "reply_formulation"
        ]
        
        for section in required_flow_sections:
            if section not in config["conversation_flow"]:
                logger.error(f"Missing conversation_flow section: {section}")
                return False
        
        # 임계값 체크
        thresholds = [
            ("conversation_flow.issue_classification.confidence_threshold", 0.0, 1.0),
            ("conversation_flow.case_narrowing.confidence_threshold", 0.0, 1.0),
            ("conversation_management.max_conversation_turns", 1, 100),
            ("conversation_management.escalation_after_failed_attempts", 1, 10)
        ]
        
        for path, min_val, max_val in thresholds:
            value = get_nested_value(config, path)
            if value is None or not (min_val <= value <= max_val):
                logger.error(f"Invalid value for {path}: {value} (should be {min_val}-{max_val})")
                return False
        
        logger.info("✅ Configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration validation error: {e}")
        return False

def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """
    중첩된 딕셔너리에서 값 추출
    
    Args:
        data: 딕셔너리 데이터
        path: 점으로 구분된 경로 (예: "section.subsection.key")
        
    Returns:
        Any: 추출된 값 또는 None
    """
    
    try:
        keys = path.split('.')
        value = data
        
        for key in keys:
            value = value[key]
        
        return value
        
    except (KeyError, TypeError):
        return None

def format_error_response(error_type: str, config: Dict[str, Any]) -> str:
    """
    오류 타입에 따른 응답 메시지 생성
    
    Args:
        error_type: 오류 타입
        config: 설정 정보
        
    Returns:
        str: 포맷된 오류 응답
    """
    
    fallback_responses = config.get("fallback_responses", {})
    
    error_mapping = {
        "classification_failed": "classification_unclear",
        "case_undetermined": "need_more_info",
        "max_questions_exceeded": "escalation",
        "max_turns_reached": "max_turns_reached",
        "session_timeout": "session_timeout",
        "general": "general_error",
        "escalation": "escalation"
    }
    
    response_key = error_mapping.get(error_type, "general_error")
    return fallback_responses.get(response_key, "죄송합니다. 오류가 발생했습니다.")

def is_session_expired(created_at: str, config: Dict[str, Any]) -> bool:
    """
    세션 만료 여부 확인
    
    Args:
        created_at: 세션 생성 시간 (ISO format)
        config: 설정 정보
        
    Returns:
        bool: 만료 여부
    """
    
    try:
        created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        current_time = datetime.now(created_time.tzinfo)
        
        timeout_minutes = config.get("conversation_management", {}).get("session_timeout_minutes", 30)
        timeout_delta = timedelta(minutes=timeout_minutes)
        
        return current_time - created_time > timeout_delta
        
    except Exception as e:
        logger.error(f"Error checking session expiry: {e}")
        return False

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    텍스트 길이 제한
    
    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        suffix: 말줄임 표시
        
    Returns:
        str: 제한된 텍스트
    """
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def sanitize_user_input(user_input: str) -> str:
    """
    사용자 입력 정제
    
    Args:
        user_input: 원본 사용자 입력
        
    Returns:
        str: 정제된 입력
    """
    
    if not user_input:
        return ""
    
    # 기본 정제: 앞뒤 공백 제거, 연속 공백 정리
    cleaned = ' '.join(user_input.strip().split())
    
    # 길이 제한 (매우 긴 입력 방지)
    if len(cleaned) > 1000:
        cleaned = cleaned[:1000]
        logger.warning(f"User input truncated to 1000 characters")
    
    return cleaned

def log_conversation_analytics(state, config: Dict[str, Any]) -> None:
    """
    대화 분석 데이터 로깅
    
    Args:
        state: 챗봇 상태
        config: 설정 정보
    """
    
    analytics_config = config.get("logging_and_analytics", {})
    
    if not analytics_config.get("track_conversation_flow", False):
        return
    
    try:
        # 대화 흐름 추적
        if analytics_config.get("track_conversation_flow"):
            logger.info(f"Analytics - Flow: {' → '.join(state.get('node_history', []))}")
        
        # 분류 정확도 추적
        if analytics_config.get("track_classification_accuracy"):
            confidence = state.get('classification_confidence', 0.0)
            issue = state.get('current_issue', 'None')
            logger.info(f"Analytics - Classification: {issue} (confidence: {confidence:.2f})")
        
        # 해결 성공률 추적
        if analytics_config.get("track_resolution_success"):
            resolved = state.get('resolution_attempted', False)
            escalated = state.get('needs_escalation', False)
            logger.info(f"Analytics - Resolution: {'Success' if resolved and not escalated else 'Failed/Escalated'}")
        
        # 에스컬레이션 이유 추적
        if analytics_config.get("track_escalation_reasons") and state.get('needs_escalation'):
            reason = state.get('escalation_reason', 'unknown')
            logger.info(f"Analytics - Escalation: {reason}")
            
    except Exception as e:
        logger.error(f"Analytics logging error: {e}")

def create_session_summary(state) -> Dict[str, Any]:
    """
    세션 요약 정보 생성
    
    Args:
        state: 챗봇 상태
        
    Returns:
        Dict[str, Any]: 세션 요약
    """
    
    return {
        "session_id": state.get('session_id'),
        "total_turns": state.get('conversation_turn', 0),
        "issue_classified": state.get('current_issue') is not None,
        "case_determined": state.get('current_case') is not None,
        "questions_asked": state.get('question_count', 0),
        "solution_provided": state.get('resolution_attempted', False),
        "escalated": state.get('needs_escalation', False),
        "escalation_reason": state.get('escalation_reason'),
        "rag_used": state.get('rag_used', False),
        "classification_confidence": state.get('classification_confidence', 0.0),
        "node_path": state.get('node_history', []),
        "duration_minutes": _calculate_session_duration(state),
        "user_satisfaction": state.get('user_satisfaction'),
        "problem_resolved": state.get('problem_resolved')
    }

def _calculate_session_duration(state) -> float:
    """
    세션 지속 시간 계산 (분 단위)
    
    Args:
        state: 챗봇 상태
        
    Returns:
        float: 지속 시간 (분)
    """
    
    try:
        created_at = state.get('created_at')
        last_updated = state.get('last_updated')
        
        if not created_at or not last_updated:
            return 0.0
        
        start_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        
        duration = end_time - start_time
        return duration.total_seconds() / 60.0
        
    except Exception as e:
        logger.error(f"Error calculating session duration: {e}")
        return 0.0