# services/azure_search.py

import os
import logging
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from langchain_openai import AzureOpenAIEmbeddings

logger = logging.getLogger(__name__)

class AzureSearchService:
    """
    Azure AI Search를 사용한 RAG 서비스
    OSS VoC 지식베이스 검색 및 컨텍스트 제공
    """
    
    def __init__(self):
        """Azure Search 클라이언트 초기화"""
        self.endpoint = os.getenv('AZURE_SEARCH_ENDPOINT')
        self.key = os.getenv('AZURE_SEARCH_KEY')
        self.index_name = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')
        
        # Embedding configuration
        self.azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_openai_key = os.getenv('AZURE_OPENAI_KEY')
        self.embedding_model = os.getenv('AZURE_OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
        
        if not self.endpoint or not self.key:
            logger.warning("Azure Search credentials not found - RAG will be disabled")
            self.client = None
            self.embeddings = None
            return
            
        try:
            self.client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=AzureKeyCredential(self.key)
            )
            
            # Initialize embeddings if Azure OpenAI is available
            if self.azure_openai_endpoint and self.azure_openai_key:
                self.embeddings = AzureOpenAIEmbeddings(
                    azure_endpoint=self.azure_openai_endpoint,
                    api_key=self.azure_openai_key,
                    azure_deployment=self.embedding_model,
                    api_version="2024-02-01"
                )
                logger.info(f"✅ Azure Search initialized with embeddings: {self.index_name}")
            else:
                self.embeddings = None
                logger.info(f"✅ Azure Search initialized without embeddings: {self.index_name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Azure Search: {e}")
            self.client = None
            self.embeddings = None
    
    def is_available(self) -> bool:
        """Azure Search 서비스 사용 가능 여부 확인"""
        return self.client is not None
    
    def search_cases(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        사용자 쿼리로 관련 케이스 검색 (Hybrid: Vector + Keyword + Semantic)
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수
            
        Returns:
            List[Dict]: 검색된 케이스들
        """
        if not self.client:
            logger.warning("Azure Search not available")
            return []
            
        try:
            # Prepare vector query if embeddings are available
            vector_queries = []
            if self.embeddings:
                try:
                    query_embedding = self.embeddings.embed_query(query)
                    vector_query = VectorizedQuery(
                        vector=query_embedding,
                        k_nearest_neighbors=top_k,
                        fields="content_vector"
                    )
                    vector_queries = [vector_query]
                    logger.info("🔢 Generated query embedding for hybrid search")
                except Exception as e:
                    logger.warning(f"Failed to generate embedding: {e}")
            
            # Hybrid search
            results = self.client.search(
                search_text=query,
                vector_queries=vector_queries,  # Empty list if no embeddings
                top=top_k,
                include_total_count=True,
                search_fields=[
                    "case_name", 
                    "description", 
                    "symptoms", 
                    "search_content",
                    "keywords"
                ],
                select=[
                    "id",
                    "issue_type", 
                    "issue_name",
                    "case_type",
                    "case_name",
                    "description",
                    "symptoms",
                    "questions_to_ask",
                    "solution_steps",
                    "escalation_triggers"
                ],
                query_type="semantic",
                semantic_configuration_name="default"
            )
            
            cases = []
            for result in results:
                case_data = {
                    'id': result.get('id'),
                    'issue_type': result.get('issue_type'),
                    'issue_name': result.get('issue_name'),
                    'case_type': result.get('case_type'),
                    'case_name': result.get('case_name'),
                    'description': result.get('description'),
                    'symptoms': result.get('symptoms', []),
                    'questions_to_ask': result.get('questions_to_ask', []),
                    'solution_steps': result.get('solution_steps', []),
                    'escalation_triggers': result.get('escalation_triggers', []),
                    'score': result.get('@search.score', 0.0),
                    'semantic_score': result.get('@search.reranker_score', 0.0)
                }
                cases.append(case_data)
                
            search_type = "hybrid" if vector_queries else "semantic"
            logger.info(f"🔍 {search_type.capitalize()} search found {len(cases)} cases for query: '{query[:50]}...'")
            return cases
            
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return []
    
    def get_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 케이스 ID로 케이스 정보 조회
        
        Args:
            case_id: 케이스 ID
            
        Returns:
            Optional[Dict]: 케이스 정보 또는 None
        """
        if not self.client:
            return None
            
        try:
            result = self.client.get_document(key=case_id)
            return result
        except Exception as e:
            logger.error(f"❌ Error getting case {case_id}: {e}")
            return None
    
    def filter_cases_by_issue_type(self, query: str, issue_type: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        특정 이슈 타입으로 필터링된 케이스 검색
        
        Args:
            query: 검색 쿼리
            issue_type: 필터링할 이슈 타입
            top_k: 반환할 최대 결과 수
            
        Returns:
            List[Dict]: 필터링된 케이스들
        """
        if not self.client:
            return []
            
        try:
            # Prepare vector query if embeddings are available
            vector_queries = []
            if self.embeddings and query:
                try:
                    query_embedding = self.embeddings.embed_query(query)
                    vector_query = VectorizedQuery(
                        vector=query_embedding,
                        k_nearest_neighbors=top_k,
                        fields="content_vector"
                    )
                    vector_queries = [vector_query]
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for filtered search: {e}")
            
            results = self.client.search(
                search_text=query,
                vector_queries=vector_queries,
                top=top_k,
                filter=f"issue_type eq '{issue_type}'",
                search_fields=[
                    "case_name", 
                    "description", 
                    "symptoms", 
                    "search_content"
                ],
                select=[
                    "id",
                    "case_type",
                    "case_name", 
                    "description",
                    "symptoms",
                    "questions_to_ask",
                    "solution_steps"
                ],
                query_type="semantic",
                semantic_configuration_name="default"
            )
            
            cases = []
            for result in results:
                case_data = {
                    'id': result.get('id'),
                    'case_type': result.get('case_type'),
                    'case_name': result.get('case_name'),
                    'description': result.get('description'),
                    'symptoms': result.get('symptoms', []),
                    'questions_to_ask': result.get('questions_to_ask', []),
                    'solution_steps': result.get('solution_steps', []),
                    'score': result.get('@search.score', 0.0),
                    'semantic_score': result.get('@search.reranker_score', 0.0)
                }
                cases.append(case_data)
                
            logger.info(f"🔍 Found {len(cases)} cases for issue '{issue_type}'")
            return cases
            
        except Exception as e:
            logger.error(f"❌ Filtered search error: {e}")
            return []
    
    def build_rag_context(self, cases: List[Dict[str, Any]], max_length: int = 2000) -> str:
        """
        검색된 케이스들로부터 RAG 컨텍스트 구성
        
        Args:
            cases: 검색된 케이스들
            max_length: 최대 컨텍스트 길이
            
        Returns:
            str: RAG 컨텍스트 텍스트
        """
        if not cases:
            return ""
            
        context_parts = []
        current_length = 0
        
        for i, case in enumerate(cases, 1):
            case_context = f"""
케이스 {i}: {case.get('case_name', 'Unknown')}
설명: {case.get('description', '')}
증상: {', '.join(case.get('symptoms', [])[:3])}
해결방법: {' '.join(case.get('solution_steps', [])[:2])}
"""
            
            if current_length + len(case_context) > max_length:
                break
                
            context_parts.append(case_context)
            current_length += len(case_context)
        
        return "\n".join(context_parts)
    
    def classify_issue_from_search(self, query: str) -> Optional[str]:
        """
        검색 결과를 기반으로 이슈 타입 분류
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            Optional[str]: 분류된 이슈 타입 또는 None
        """
        cases = self.search_cases(query, top_k=3)
        
        if not cases:
            return None
            
        # 가장 높은 스코어의 케이스에서 이슈 타입 추출
        best_case = max(cases, key=lambda x: x.get('score', 0))
        
        if best_case.get('score', 0) > 0.5:  # 임계값 설정
            return best_case.get('issue_type')
            
        return None
    
    def get_related_questions(self, issue_type: str, case_type: Optional[str] = None) -> List[str]:
        """
        특정 이슈/케이스에 대한 관련 질문들 조회
        
        Args:
            issue_type: 이슈 타입
            case_type: 케이스 타입 (선택적)
            
        Returns:
            List[str]: 관련 질문들
        """
        if not self.client:
            return []
        
        try:
            filter_condition = f"issue_type eq '{issue_type}'"
            if case_type:
                filter_condition += f" and case_type eq '{case_type}'"
            
            results = self.client.search(
                search_text="*",
                filter=filter_condition,
                select=["questions_to_ask"]
            )
            
            all_questions = []
            for result in results:
                questions = result.get('questions_to_ask', [])
                all_questions.extend(questions)
            
            # 중복 제거 및 반환
            return list(set(all_questions))
            
        except Exception as e:
            logger.error(f"❌ Error getting related questions: {e}")
            return []

# 전역 인스턴스 생성
search_service = AzureSearchService()