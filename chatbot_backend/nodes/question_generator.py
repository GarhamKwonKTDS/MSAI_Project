# nodes/question_generator.py

import logging
from typing import Dict, Any, List, Optional
from langchain_openai import AzureChatOpenAI
from models.state import ChatbotState, update_state_metadata
from services.azure_search import search_service

logger = logging.getLogger(__name__)

def question_generation_node(state: ChatbotState, config: Dict[str, Any], llm: AzureChatOpenAI) -> ChatbotState:
    """
    질문 생성 노드 - 케이스 확정을 위한 적절한 질문 생성
    
    프로세스:
    1. 최대 질문 수 체크 (무한 루프 방지)
    2. 현재 이슈/케이스 후보들에서 관련 질문들 수집
    3. 이미 묻지 않은 질문들 중에서 가장 적절한 질문 선택
    4. LLM으로 맥락에 맞는 자연스러운 질문 생성
    
    Args:
        state: 현재 챗봇 상태
        config: 대화 설정 정보
        llm: Azure OpenAI LLM 인스턴스
        
    Returns:
        ChatbotState: 업데이트된 상태
    """
    
    # 메타데이터 업데이트
    state = update_state_metadata(state, "question_generation")
    
    logger.info(f"❓ Question Generation - Question #{state['question_count'] + 1}")
    logger.info(f"   Current Issue: {state['current_issue']}")
    logger.info(f"   Questions Asked: {len(state['questions_asked'])}")
    
    try:
        # 1. 최대 질문 수 체크
        max_questions = config['conversation_flow']['case_narrowing']['max_questions_per_case']
        if state['question_count'] >= max_questions:
            logger.warning(f"   ⚠️ Max questions reached ({max_questions}) - escalating")
            state['needs_escalation'] = True
            state['escalation_reason'] = "max_questions_exceeded"
            state['final_response'] = config['fallback_responses']['escalation']
            return state
        
        # 2. 관련 질문들 수집
        candidate_questions = _collect_candidate_questions(state, config)
        
        if not candidate_questions:
            logger.warning("   ⚠️ No candidate questions found - escalating")
            state['needs_escalation'] = True
            state['escalation_reason'] = "no_questions_available"
            state['final_response'] = config['fallback_responses']['escalation']
            return state
        
        # 3. 최적 질문 선택
        selected_question = _select_best_question(
            state, 
            candidate_questions, 
            config, 
            llm
        )
        
        if selected_question:
            # 4. 질문을 자연스럽게 다듬기
            final_question = _refine_question(
                selected_question, 
                state, 
                config, 
                llm
            )
            
            # 상태 업데이트
            state['final_response'] = final_question
            state['questions_asked'].append(selected_question)
            state['question_count'] += 1
            
            logger.info(f"   ✅ Question generated: {final_question[:100]}...")
            
        else:
            logger.warning("   ⚠️ Could not select appropriate question - escalating")
            state['needs_escalation'] = True
            state['escalation_reason'] = "question_selection_failed"
            state['final_response'] = config['fallback_responses']['escalation']
        
    except Exception as e:
        logger.error(f"   ❌ Question generation error: {e}")
        state['error_count'] += 1
        
        if state['error_count'] < 3:
            state['final_response'] = config['fallback_responses']['need_more_info']
        else:
            state['needs_escalation'] = True
            state['escalation_reason'] = "too_many_errors"
            state['final_response'] = config['fallback_responses']['escalation']
    
    return state

def _collect_candidate_questions(state: ChatbotState, config: Dict[str, Any]) -> List[str]:
    """
    후보 질문들 수집
    
    Args:
        state: 현재 챗봇 상태
        config: 설정 정보
        
    Returns:
        List[str]: 후보 질문들
    """
    
    candidate_questions = []
    
    # 1. Azure Search에서 관련 질문들 가져오기
    if state['current_issue']:
        search_questions = search_service.get_related_questions(
            issue_type=state['current_issue'],
            case_type=state.get('current_case')
        )
        candidate_questions.extend(search_questions)
    
    # 2. 검색된 케이스들에서 질문 추출
    for case in state.get('retrieved_cases', []):
        case_questions = case.get('questions_to_ask', [])
        candidate_questions.extend(case_questions)
    
    # 3. 중복 제거 및 이미 물어본 질문 필터링
    unique_questions = []
    asked_questions_lower = [q.lower() for q in state['questions_asked']]
    
    for question in candidate_questions:
        if question and question.lower() not in asked_questions_lower:
            if question not in unique_questions:
                unique_questions.append(question)
    
    logger.info(f"   📋 Found {len(unique_questions)} candidate questions")
    return unique_questions

def _select_best_question(
    state: ChatbotState, 
    questions: List[str], 
    config: Dict[str, Any], 
    llm: AzureChatOpenAI
) -> Optional[str]:
    """
    가장 적합한 질문 선택
    
    Args:
        state: 현재 챗봇 상태
        questions: 후보 질문들
        config: 설정 정보
        llm: LLM 인스턴스
        
    Returns:
        Optional[str]: 선택된 질문 또는 None
    """
    
    if not questions:
        return None
    
    # 질문이 하나뿐이면 바로 반환
    if len(questions) == 1:
        return questions[0]
    
    # 전략에 따른 질문 선택
    selection_strategy = config['conversation_flow']['case_narrowing'].get('question_selection_strategy', 'progressive')
    
    if selection_strategy == 'progressive':
        return _select_progressive_question(state, questions, llm)
    else:
        # 기본적으로 첫 번째 질문 선택
        return questions[0]

def _select_progressive_question(
    state: ChatbotState, 
    questions: List[str], 
    llm: AzureChatOpenAI
) -> Optional[str]:
    """
    점진적 전략으로 질문 선택 - LLM이 맥락에 가장 적합한 질문 선택
    
    Args:
        state: 현재 챗봇 상태
        questions: 후보 질문들
        llm: LLM 인스턴스
        
    Returns:
        Optional[str]: 선택된 질문
    """
    
    # 대화 맥락 구성
    context = _build_question_context(state)
    
    # 질문 목록 구성
    question_list = []
    for i, question in enumerate(questions[:5], 1):  # 최대 5개만
        question_list.append(f"{i}. {question}")
    
    prompt = f"""
다음은 현재 대화 상황입니다:
{context}

사용자의 문제를 정확히 파악하기 위해 다음 중 가장 적절한 질문을 선택하세요:

{chr(10).join(question_list)}

선택 기준:
- 현재 상황에서 가장 중요한 정보를 얻을 수 있는 질문
- 사용자가 쉽게 답할 수 있는 질문
- 케이스 확정에 가장 도움이 되는 질문

다음 형식으로 답변하세요:
선택: [번호]
이유: [선택 이유]
"""
    
    try:
        response = llm.invoke(prompt)
        result = response.content.strip()
        
        # 응답에서 번호 추출
        lines = result.split('\n')
        for line in lines:
            if line.strip().startswith('선택:'):
                try:
                    number = int(line.replace('선택:', '').strip())
                    if 1 <= number <= len(questions):
                        selected_question = questions[number - 1]
                        logger.info(f"   🎯 LLM selected question #{number}")
                        return selected_question
                except ValueError:
                    pass
        
        # 파싱 실패시 첫 번째 질문 반환
        logger.warning("   ⚠️ Failed to parse LLM selection, using first question")
        return questions[0]
        
    except Exception as e:
        logger.error(f"Question selection error: {e}")
        return questions[0]

def _build_question_context(state: ChatbotState) -> str:
    """
    질문 선택을 위한 대화 맥락 구성
    
    Args:
        state: 현재 챗봇 상태
        
    Returns:
        str: 대화 맥락
    """
    
    context_parts = []
    
    context_parts.append(f"문제 유형: {state['current_issue']}")
    context_parts.append(f"사용자 메시지: {state['user_message']}")
    
    if state['gathered_info']:
        context_parts.append("이미 수집된 정보:")
        for key, info in state['gathered_info'].items():
            if isinstance(info, dict):
                context_parts.append(f"- {info.get('question', '')}: {info.get('answer', '')}")
    
    if state['answers_received']:
        context_parts.append(f"최근 답변: {state['answers_received'][-1]}")
    
    return "\n".join(context_parts)

def _refine_question(
    question: str, 
    state: ChatbotState, 
    config: Dict[str, Any], 
    llm: AzureChatOpenAI
) -> str:
    """
    질문을 자연스럽고 맥락에 맞게 다듬기
    
    Args:
        question: 원본 질문
        state: 현재 챗봇 상태
        config: 설정 정보
        llm: LLM 인스턴스
        
    Returns:
        str: 다듬어진 질문
    """
    
    # 설정에서 응답 스타일 가져오기
    tone = config['response_formatting']['tone']
    language_style = config['response_formatting']['language_style']
    
    gathering_strategy = config['conversation_flow']['case_narrowing']['information_gathering_strategy']
    
    prompt = f"""
다음 질문을 더 자연스럽고 도움이 되도록 다듬어 주세요:

원본 질문: "{question}"

요구사항:
- 톤: {tone}
- 언어 스타일: {language_style}
- 전략: {gathering_strategy}

현재 상황: 사용자가 {state['current_issue']} 문제를 겪고 있으며, {state['question_count']}번째 질문입니다.

다듬어진 질문:
"""
    
    try:
        response = llm.invoke(prompt)
        refined_question = response.content.strip()
        
        # 기본 검증 (너무 길면 원본 사용)
        if len(refined_question) > 200:
            return question
            
        return refined_question
        
    except Exception as e:
        logger.error(f"Question refinement error: {e}")
        return question