# setup_search_index.py - Hybrid Vector + Semantic Search Setup

import os
import json
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticConfiguration,
    SemanticField,
    SemanticSearch,
    SemanticPrioritizedFields,
    SearchField,
    VectorSearchAlgorithmKind
)
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_ENDPOINT')
SEARCH_KEY = os.getenv('AZURE_SEARCH_KEY')
INDEX_NAME = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')

# Embedding configuration
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
EMBEDDING_MODEL = os.getenv('AZURE_OPENAI_EMBEDDING_MODEL', 'text-embedding-ada-002')

# Initialize embeddings
embeddings = AzureOpenAIEmbeddings(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    azure_deployment=EMBEDDING_MODEL,
    api_version="2024-02-01"
)

def create_search_index():
    """Create the search index with vector and semantic search capabilities"""
    
    print(f"🔍 Creating hybrid search index: {INDEX_NAME}")
    
    # Initialize the index client
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    # Define the index schema with vector field
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="issue_type", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="issue_name", type=SearchFieldDataType.String),
        SimpleField(name="case_type", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="case_name", type=SearchFieldDataType.String),
        SearchableField(name="description", type=SearchFieldDataType.String),
        SearchableField(name="search_content", type=SearchFieldDataType.String),
        
        # Array fields - using SearchField with Collection type
        SearchField(
            name="keywords",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True
        ),
        SearchField(
            name="symptoms",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True
        ),
        SearchField(
            name="questions_to_ask",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True
        ),
        SearchField(
            name="solution_steps",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True
        ),
        SearchField(
            name="escalation_triggers",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True
        ),
        
        # Vector field for embeddings (1536 dimensions for ada-002)
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="myHnswProfile"
        )
    ]
    
    # Configure vector search
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw"
            )
        ]
    )
    
    # Configure semantic search
    semantic_config = SemanticConfiguration(
        name="default",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="case_name"),
            content_fields=[
                SemanticField(field_name="description"),
                SemanticField(field_name="search_content")
            ],
            keywords_fields=[SemanticField(field_name="keywords")]
        )
    )
    
    # Create the index with both vector and semantic search
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=SemanticSearch(configurations=[semantic_config])
    )
    
    try:
        result = index_client.create_or_update_index(index)
        print(f"✅ Index '{result.name}' created with hybrid search capabilities!")
        return True
    except Exception as e:
        print(f"❌ Error creating index: {e}")
        return False

def generate_embeddings(text: str) -> list:
    """Generate embeddings for text using Azure OpenAI"""
    try:
        embedding = embeddings.embed_query(text)
        return embedding
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        return None

def load_knowledge_base():
    """Load our knowledge base data"""
    
    knowledge_base = [
        {
            "id": "oss_login_password_expired_90days",
            "issue_type": "oss_login_failure",
            "issue_name": "OSS 로그인 문제",
            "case_type": "password_expired_90days",
            "case_name": "90일 비밀번호 만료",
            "description": "OSS 비밀번호가 90일 주기로 만료되어 변경이 필요한 상황",
            "keywords": ["90일만료", "비밀번호만료", "password expired", "주기만료", "비번만료"],
            "symptoms": [
                "비밀번호가 만료되었다는 메시지가 나옴",
                "90일이 지나서 로그인이 안됨",
                "비밀번호 변경하라고 나오는데 변경 화면으로 안 넘어감",
                "로그인 시 '비밀번호를 변경하세요' 팝업"
            ],
            "questions_to_ask": [
                "마지막으로 비밀번호를 변경한 날짜를 기억하시나요?",
                "비밀번호 변경 화면은 표시되나요?",
                "변경하려는 새 비밀번호가 정책에 맞나요? (영문/숫자/특수문자 조합)",
                "이전에 사용했던 비밀번호를 다시 사용하려고 하시나요?"
            ],
            "solution_steps": [
                "1. OSS 로그인 화면에서 '비밀번호 변경' 링크를 클릭합니다",
                "2. 현재 비밀번호를 입력합니다",
                "3. 새 비밀번호는 영문/숫자/특수문자 조합 8자 이상으로 설정합니다",
                "4. 최근 3개월 내 사용한 비밀번호는 재사용할 수 없습니다",
                "5. 변경 완료 후 새 비밀번호로 로그인합니다"
            ],
            "escalation_triggers": [
                "비밀번호 변경 화면이 표시되지 않는 경우",
                "정책에 맞는 비밀번호인데도 변경이 안 되는 경우",
                "변경 후에도 로그인이 안 되는 경우"
            ],
            "search_content": "OSS 로그인 문제 90일 비밀번호 만료 90일만료 비밀번호만료 password expired 주기만료 비번만료 OSS 비밀번호가 90일 주기로 만료되어 변경이 필요한 상황"
        },
        {
            "id": "oss_login_new_employee_account_delay",
            "issue_type": "oss_login_failure",
            "issue_name": "OSS 로그인 문제",
            "case_type": "new_employee_account_delay",
            "case_name": "신규 입사자 계정 생성 지연",
            "description": "신규 입사자가 IDMS 계정 신청 후 OSS 시스템 동기화 대기 중인 상황",
            "keywords": ["신규입사", "신입사원", "계정생성", "입사자", "신규직원", "계정없음", "IDMS신청", "익일반영", "동기화"],
            "symptoms": [
                "오늘 IDMS에서 계정 신청했는데 OSS 로그인이 안됨",
                "IDMS 계정은 만들어졌는데 OSS에서 사번을 찾을 수 없음",
                "동료가 어제 신청하면 오늘 되던데 나는 안됨",
                "KT 협력사로 IDMS 가입은 완료했는데 OSS 접속 불가"
            ],
            "questions_to_ask": [
                "IDMS에서 KT 협력사로 계정 신청은 완료하셨나요?",
                "IDMS 계정 신청을 정확히 언제 하셨나요? (날짜/시간)",
                "IDMS에서 발급받은 사번이 무엇인가요?",
                "혹시 오늘 오후나 저녁에 신청하셨나요?"
            ],
            "solution_steps": [
                "1. IDMS에서 KT 협력사로 계정이 정상 생성되었는지 확인합니다",
                "2. OSS 시스템은 매일 새벽에 IDMS 사용자 정보를 동기화합니다",
                "3. 오늘 IDMS 신청을 완료했다면 내일 오전부터 OSS 로그인이 가능합니다",
                "4. 익일 OSS 시스템에서 IDMS에 등록한 사번으로 로그인을 시도합니다",
                "5. 첫 로그인 시 OSS 내 추가 정보 입력이 필요할 수 있습니다"
            ],
            "escalation_triggers": [
                "IDMS 신청 후 2일 이상 지났는데도 OSS 로그인이 안 되는 경우",
                "긴급 업무로 당일 접속이 반드시 필요한 경우",
                "IDMS와 OSS 간 동기화 오류가 의심되는 경우",
                "매일 새벽 동기화가 실행되지 않은 것으로 의심되는 경우"
            ],
            "search_content": "OSS 로그인 문제 신규 입사자 계정 생성 지연 신규입사 신입사원 계정생성 입사자 신규직원 계정없음 IDMS신청 익일반영 동기화 신규 입사자가 IDMS 계정 신청 후 OSS 시스템 동기화 대기 중인 상황"
        },
        {
            "id": "oss_permission_menu_access_denied",
            "issue_type": "oss_permission_request",
            "issue_name": "OSS 권한 신청",
            "case_type": "menu_access_denied",
            "case_name": "특정 메뉴 접근 권한 없음",
            "description": "OSS 업무팀 가입은 완료했지만 업무에 필요한 특정 메뉴나 기능에 접근할 수 없는 상황",
            "keywords": ["메뉴권한", "접근거부", "권한없음", "메뉴안보임", "기능사용불가", "Access Denied", "권한신청", "개인권한"],
            "symptoms": [
                "업무팀 가입은 승인되었는데 필요한 메뉴가 보이지 않음",
                "팀원들은 사용하는 기능인데 나만 '권한이 없습니다' 메시지가 표시됨",
                "업무팀은 'CS지원팀'인데 서비스 처리 메뉴가 안 보임",
                "특정 버튼을 클릭하면 접근 거부 오류",
                "팀 권한은 있는데 개인 권한이 없다고 나옴",
                "권한을 어떻게 신청하는지 모르겠음"
            ],
            "questions_to_ask": [
                "현재 가입된 업무팀이 무엇인가요?",
                "업무팀 가입 승인은 언제 받으셨나요?",
                "어떤 메뉴나 기능에 접근하려고 하시나요?",
                "같은 팀 동료들은 해당 메뉴를 정상적으로 사용하나요?",
                "개인 권한을 별도로 신청한 적이 있으신가요?"
            ],
            "solution_steps": [
                "1. OSS 내 '권한신청' 메뉴로 이동합니다",
                "2. 개인권한신청 항목을 선택합니다",
                "3. 필요한 메뉴/기능의 권한을 검색하여 선택합니다",
                "4. 신청 사유를 작성하고 결재자를 지정합니다",
                "5. 승인 완료 후 로그아웃/로그인하여 권한을 새로고침합니다"
            ],
            "escalation_triggers": [
                "긴급 업무인데 결재자가 부재중인 경우",
                "권한신청 메뉴 자체에 접근할 수 없는 경우",
                "승인이 완료되었는데도 권한이 반영되지 않는 경우",
                "업무팀 권한과 개인 권한이 충돌하는 경우"
            ],
            "search_content": "OSS 권한 신청 특정 메뉴 접근 권한 없음 메뉴권한 접근거부 권한없음 메뉴안보임 기능사용불가 Access Denied 권한신청 개인권한 OSS 업무팀 가입은 완료했지만 업무에 필요한 특정 메뉴나 기능에 접근할 수 없는 상황"
        },
        {
            "id": "oss_permission_no_team_cant_request",
            "issue_type": "oss_permission_request",
            "issue_name": "OSS 권한 신청",
            "case_type": "no_team_cant_request",
            "case_name": "업무팀 미가입으로 권한신청 불가",
            "description": "업무팀에 가입하지 않았거나 승인받지 못해 권한 신청 자체를 할 수 없는 상황",
            "keywords": ["권한신청불가", "팀없음", "업무팀미가입", "권한신청안됨", "팀가입필요", "권한메뉴없음"],
            "symptoms": [
                "권한을 신청하려는데 권한신청 메뉴가 없음",
                "아직 업무팀에 가입하지 않았음",
                "업무팀 가입 신청은 했는데 아직 승인 대기중",
                "권한이 필요한데 어디서부터 시작해야 할지 모르겠음"
            ],
            "questions_to_ask": [
                "현재 업무팀에 가입되어 있나요?",
                "업무팀 가입 신청을 하신 적이 있나요?",
                "업무팀 가입 신청을 했다면 언제 하셨나요?",
                "어떤 업무를 위해 권한이 필요하신가요?",
                "소속 부서의 업무팀 이름을 알고 계신가요?"
            ],
            "solution_steps": [
                "1. 먼저 OSS '업무팀 조회' 메뉴에서 가입할 업무팀을 검색합니다",
                "2. 적절한 업무팀을 선택하여 가입 신청을 합니다",
                "3. 팀 관리자의 승인을 기다립니다 (보통 1-2일)",
                "4. 업무팀 가입이 승인되면 '권한신청' 메뉴가 활성화됩니다",
                "5. 이제 필요한 개인 권한을 신청할 수 있습니다"
            ],
            "escalation_triggers": [
                "어떤 업무팀에 가입해야 하는지 모르는 경우",
                "업무팀 승인이 3일 이상 지연되는 경우",
                "긴급히 권한이 필요한데 업무팀 절차 때문에 막힌 경우",
                "임시 권한이나 예외 처리가 필요한 경우"
            ],
            "search_content": "OSS 권한 신청 업무팀 미가입으로 권한신청 불가 권한신청불가 팀없음 업무팀미가입 권한신청안됨 팀가입필요 권한메뉴없음 업무팀에 가입하지 않았거나 승인받지 못해 권한 신청 자체를 할 수 없는 상황"
        },
        {
            "id": "oss_permission_customer_info_masked",
            "issue_type": "oss_permission_request",
            "issue_name": "OSS 권한 신청",
            "case_type": "customer_info_masked",
            "case_name": "고객정보 조회 시 마스킹 처리",
            "description": "OSS에서 고객 정보 조회 시 개인정보가 *** 처리되어 업무 수행이 불가능한 상황",
            "keywords": ["마스킹", "개인정보", "***처리", "고객정보", "숨김처리", "정보조회", "개인정보권한", "마스킹해제"],
            "symptoms": [
                "개인정보 권한이 없어요",
                "업무를 해야 하는데 개인정보 마스킹 해제 권한이 없어요",
                "고객 응대 업무인데 개인정보 조회 권한이 없다고 나와요",
                "마스킹 해제 권한을 어떻게 신청하는지 모르겠어요",
                "개인정보 권한 신청을 하려는데 2차 승인자가 누군지 몰라요"
            ],
            "questions_to_ask": [
                "개인정보 조회 권한을 신청한 적이 있나요?",
                "현재 담당 업무가 고객 응대 업무인가요?",
                "개인정보보호 교육을 이수하셨나요?",
                "소속 부서와 담당 업무가 무엇인가요?",
                "이전에는 정상적으로 조회되었나요?"
            ],
            "solution_steps": [
                "1. '권한신청' 메뉴에서 '개인정보 조회 권한'을 신청합니다",
                "2. 신청 사유에 업무 필요성을 구체적으로 작성합니다",
                "3. 1차 승인자(팀장)와 2차 승인자(개인정보보호책임자)를 지정합니다",
                "4. 개인정보보호 서약서를 작성하고 제출합니다",
                "5. 승인 완료 후 마스킹이 해제되어 전체 정보 조회가 가능합니다"
            ],
            "escalation_triggers": [
                "2차 승인자가 누구인지 모르는 경우",
                "개인정보보호 교육 이수 여부가 불분명한 경우",
                "승인은 받았는데 여전히 마스킹되는 경우",
                "긴급 고객 응대로 즉시 권한이 필요한 경우"
            ],
            "search_content": "OSS 권한 신청 고객정보 조회 시 마스킹 처리 마스킹 개인정보 ***처리 고객정보 숨김처리 정보조회 개인정보권한 마스킹해제 OSS에서 고객 정보 조회 시 개인정보가 *** 처리되어 업무 수행이 불가능한 상황"
        },
        {
            "id": "oss_login_8sabun_access_denied",
            "issue_type": "oss_login_failure",
            "issue_name": "OSS 로그인 문제",
            "case_type": "8sabun_access_denied",
            "case_name": "KT 그룹사 8사번으로 OSS 접근 불가",
            "description": "KT 그룹사 직원이 8사번으로 OSS 접속을 시도했으나 거부되는 상황 (KTDS 제외)",
            "keywords": ["8사번", "그룹사", "접속불가", "로그인거부", "9사번필요", "협력사계정", "KTDS제외"],
            "symptoms": [
                "KT 그룹사 직원인데 8사번으로 OSS 로그인이 안돼요",
                "8사번으로 로그인하면 '권한이 없습니다' 메시지가 나와요",
                "KTDS 동료는 8사번으로 되는데 우리 회사는 안돼요",
                "OSS 사용하려면 9사번을 만들어야 한다고 하는데 어떻게 하나요",
                "그룹사 직원인데 왜 협력사 계정을 만들어야 하나요"
            ],
            "questions_to_ask": [
                "어느 KT 그룹사 소속이신가요?",
                "KTDS 직원이신가요?",
                "현재 8로 시작하는 사번을 가지고 계신가요?",
                "IDMS에서 협력사 계정을 만든 적이 있나요?",
                "9사번을 이미 발급받으셨나요?"
            ],
            "solution_steps": [
                "1. KTDS 직원이 아닌 경우 8사번으로는 OSS 접속이 불가합니다",
                "2. IDMS에 접속하여 'KT 협력사' 계정을 신규 생성합니다",
                "3. 협력사 계정 생성 시 9로 시작하는 사번이 발급됩니다",
                "4. 익일부터 9사번으로 OSS 로그인이 가능합니다",
                "5. 기존 8사번과 별개로 9사번을 OSS 전용으로 사용합니다"
            ],
            "escalation_triggers": [
                "KTDS 직원인데 8사번 로그인이 안 되는 경우",
                "9사번 생성 후에도 로그인이 안 되는 경우",
                "그룹사 정책 변경으로 인한 혼란이 있는 경우",
                "시스템이 KTDS를 구분하지 못하는 경우"
            ],
            "search_content": "OSS 로그인 문제 KT 그룹사 8사번으로 OSS 접근 불가 8사번 그룹사 접속불가 로그인거부 9사번필요 협력사계정 KTDS제외 KT 그룹사 직원이 8사번으로 OSS 접속을 시도했으나 거부되는 상황 (KTDS 제외)"
        }
    ]
    
    print(f"📚 Loaded {len(knowledge_base)} knowledge base entries")
    return knowledge_base

def upload_knowledge_base_with_embeddings():
    """Upload knowledge base to Azure AI Search with embeddings"""
    
    print("📤 Uploading knowledge base with embeddings...")
    
    # Initialize search client
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    # Load knowledge base
    documents = load_knowledge_base()
    
    # Generate embeddings for each document
    for doc in documents:
        # Create combined text for embedding
        embedding_text = f"{doc['case_name']} {doc['description']} {doc['search_content']}"
        
        # Generate embedding
        print(f"🔄 Generating embedding for: {doc['id']}")
        embedding = generate_embeddings(embedding_text)
        
        if embedding:
            doc['content_vector'] = embedding
        else:
            print(f"⚠️ Failed to generate embedding for {doc['id']}")
    
    try:
        # Upload documents
        result = search_client.upload_documents(documents=documents)
        
        # Check results
        success_count = sum(1 for r in result if r.succeeded)
        total_count = len(result)
        
        print(f"✅ Upload completed: {success_count}/{total_count} documents uploaded successfully")
        
        if success_count < total_count:
            print("❌ Some documents failed to upload:")
            for r in result:
                if not r.succeeded:
                    print(f"   - {r.key}: {r.error_message}")
        
        return success_count == total_count
        
    except Exception as e:
        print(f"❌ Error uploading documents: {e}")
        return False

def test_hybrid_search():
    """Test the hybrid search functionality"""
    
    print("🧪 Testing hybrid search functionality...")
    
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    # Test queries
    test_queries = [
        "OSS 로그인이 안 돼요",
        "비밀번호를 잊어버렸어요",
        "권한이 필요해요"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        
        # Generate query embedding
        query_embedding = generate_embeddings(query)
        
        if not query_embedding:
            print("   ❌ Failed to generate query embedding")
            continue
        
        try:
            # Hybrid search: vector + keyword + semantic
            from azure.search.documents.models import VectorizedQuery
            
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=3,
                fields="content_vector"
            )
            
            results = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                query_type="semantic",
                semantic_configuration_name="default",
                top=3,
                select=["id", "case_name", "description"]
            )
            
            print(f"   Hybrid search results:")
            for i, result in enumerate(results, 1):
                score = result.get('@search.score', 0)
                reranker_score = result.get('@search.reranker_score', 0)
                print(f"   {i}. {result['case_name']} (Score: {score:.2f}, Semantic: {reranker_score:.2f})")
                print(f"      {result['description'][:100]}...")
                
        except Exception as e:
            print(f"   ❌ Search error: {e}")

def main():
    """Main execution function"""
    
    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        print("❌ Missing Azure Search configuration!")
        print("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY environment variables")
        return False
    
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY:
        print("❌ Missing Azure OpenAI configuration for embeddings!")
        print("Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY environment variables")
        return False
    
    print("🚀 Setting up Azure AI Search with Hybrid Search (Vector + Semantic)...")
    print(f"   Search Endpoint: {SEARCH_ENDPOINT}")
    print(f"   Index: {INDEX_NAME}")
    print(f"   Embedding Model: {EMBEDDING_MODEL}")
    
    # Step 1: Create index with vector and semantic capabilities
    if not create_search_index():
        return False
    
    # Step 2: Upload knowledge base with embeddings
    if not upload_knowledge_base_with_embeddings():
        return False
    
    # Step 3: Test hybrid search
    test_hybrid_search()
    
    print("\n🎉 Azure AI Search with hybrid search setup completed successfully!")
    print("Your Flask app can now use vector + semantic search!")
    
    return True

if __name__ == "__main__":
    main()