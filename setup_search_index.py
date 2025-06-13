# Search Index Setup and Knowledge Base Upload
# setup_search_index.py

import os
import json
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    ComplexField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_ENDPOINT')
SEARCH_KEY = os.getenv('AZURE_SEARCH_KEY')
INDEX_NAME = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')

def create_search_index():
    """Create the search index with proper schema"""
    
    print(f"🔍 Creating search index: {INDEX_NAME}")
    
    # Initialize the index client
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    # Define the index schema
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="issue_type", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="issue_name", type=SearchFieldDataType.String),
        SimpleField(name="case_type", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="case_name", type=SearchFieldDataType.String),
        SearchableField(name="description", type=SearchFieldDataType.String),
        SearchableField(name="keywords", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
        SearchableField(name="symptoms", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
        SearchableField(name="questions_to_ask", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
        SearchableField(name="solution_steps", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
        SearchableField(name="escalation_triggers", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
        SearchableField(name="search_content", type=SearchFieldDataType.String),
    ]
    
    # Create the index
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields
    )
    
    try:
        result = index_client.create_or_update_index(index)
        print(f"✅ Index '{result.name}' created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating index: {e}")
        return False

def load_knowledge_base():
    """Load our knowledge base data"""
    
    # Our knowledge base (the 8 cases we defined earlier)
    knowledge_base = [
        {
            "id": "oss_login_new_account_needed",
            "issue_type": "oss_login_failure",
            "issue_name": "OSS 로그인 문제",
            "case_type": "new_account_needed",
            "case_name": "신규 계정 신청 필요",
            "description": "OSS/NEOSS 로그인을 위해 IDMS에서 신규 계정 신청 및 승인이 필요한 상황",
            "keywords": ["넷코어", "OSS-OM", "로그인 불가", "신규계정", "9시작 사번", "IDMS", "계정신청", "승인"],
            "symptoms": [
                "OSS-OM에 처음 로그인하려고 함",
                "계정이 없다고 나옴",
                "사용자를 찾을 수 없다는 메시지",
                "9시작 사번이 없음"
            ],
            "questions_to_ask": [
                "이전에 OSS/NEOSS에 로그인한 적이 있나요?",
                "IDMS에서 계정을 신청하셨나요?",
                "9시작 사번을 받으셨나요?",
                "언제 계정 신청을 하셨나요?"
            ],
            "solution_steps": [
                "1. OSS/NEOSS 로그인 시 9시작 사번이 필요합니다",
                "2. IDMS 부서에 계정 신청을 요청하세요",
                "3. 계정 승인 완료를 기다리세요",
                "4. 승인 완료 후 9시작 사번으로 로그인하세요"
            ],
            "escalation_triggers": [
                "계정 신청이 지연되는 경우",
                "긴급 업무로 즉시 계정이 필요한 경우",
                "IDMS 프로세스에 문제가 있는 경우"
            ],
            "search_content": "OSS 로그인 문제 신규 계정 신청 필요 넷코어 OSS-OM 로그인 불가 신규계정 9시작 사번 IDMS 계정신청 승인 OSS/NEOSS 로그인을 위해 IDMS에서 신규 계정 신청 및 승인이 필요한 상황"
        },
        {
            "id": "oss_login_password_issues",
            "issue_type": "oss_login_failure",
            "issue_name": "OSS 로그인 문제",
            "case_type": "password_issues",
            "case_name": "비밀번호 문제",
            "description": "OSS 로그인 시 비밀번호 오류, 계정 잠김, 비밀번호 재설정이 필요한 모든 상황",
            "keywords": ["비밀번호틀림", "암호변경", "비밀번호오류", "계정잠김", "비번실패횟수", "5회초과", "OTP", "초기화"],
            "symptoms": [
                "비밀번호가 틀리다고 나옴",
                "계정이 잠겼다는 메시지",
                "비밀번호 실패 횟수 5회 초과",
                "비밀번호를 기억하지 못함",
                "로그인 시도가 차단됨"
            ],
            "questions_to_ask": [
                "비밀번호를 정확히 입력하고 계신가요?",
                "몇 번 정도 로그인을 시도하셨나요?",
                "계정 잠김 관련 메시지를 받으셨나요?",
                "OTP 문자를 받을 수 있나요?"
            ],
            "solution_steps": [
                "1. 비밀번호 입력 시 대소문자와 특수문자를 정확히 확인하세요",
                "2. 계정이 잠긴 경우: 비밀번호 실패 횟수 초기화를 진행하세요",
                "3. OTP 문자를 받아 인증을 완료하세요",
                "4. 비밀번호 확인이 불가능할 경우 로그인 화면에서 암호 변경을 진행하세요",
                "5. 새 비밀번호로 로그인하세요"
            ],
            "escalation_triggers": [
                "OTP 문자를 받지 못하는 경우",
                "암호 변경 기능이 작동하지 않는 경우",
                "반복적으로 계정이 잠기는 경우"
            ],
            "search_content": "OSS 로그인 문제 비밀번호 문제 비밀번호틀림 암호변경 비밀번호오류 계정잠김 비번실패횟수 5회초과 OTP 초기화 OSS 로그인 시 비밀번호 오류, 계정 잠김, 비밀번호 재설정이 필요한 모든 상황"
        },
        {
            "id": "oss_login_approval_pending",
            "issue_type": "oss_login_failure",
            "issue_name": "OSS 로그인 문제",
            "case_type": "approval_pending",
            "case_name": "승인 대기 중",
            "description": "IDMS에서 계정 신청을 했지만 아직 승인이 완료되지 않아 로그인할 수 없는 상황",
            "keywords": ["승인대기", "계정승인", "IDMS승인", "익일로그인", "승인완료"],
            "symptoms": [
                "IDMS에서 계정을 신청했지만 로그인 안 됨",
                "계정 승인이 완료되지 않음",
                "당일 신청했는데 로그인 안 됨",
                "승인 상태를 확인하고 싶음"
            ],
            "questions_to_ask": [
                "언제 IDMS에서 계정을 신청하셨나요?",
                "승인 완료 통지를 받으셨나요?",
                "계정 승인 상태를 확인해보셨나요?",
                "긴급하게 로그인이 필요한 업무인가요?"
            ],
            "solution_steps": [
                "1. IDMS에서 계정 승인 상태를 확인하세요",
                "2. 당일 승인받은 경우 익일 로그인이 가능합니다",
                "3. 승인이 완료되지 않은 경우 승인 담당자에게 문의하세요",
                "4. 승인 완료 후 9시작 사번으로 로그인하세요"
            ],
            "escalation_triggers": [
                "승인이 비정상적으로 지연되는 경우",
                "승인 완료 후에도 로그인이 안 되는 경우",
                "긴급 업무로 즉시 승인이 필요한 경우"
            ],
            "search_content": "OSS 로그인 문제 승인 대기 중 승인대기 계정승인 IDMS승인 익일로그인 승인완료 IDMS에서 계정 신청을 했지만 아직 승인이 완료되지 않아 로그인할 수 없는 상황"
        },
        {
            "id": "oss_permission_personal_authority",
            "issue_type": "oss_permission_request",
            "issue_name": "OSS 권한 신청",
            "case_type": "personal_authority_request",
            "case_name": "개인 권한 신청",
            "description": "OSS에서 서비스 수행 처리나 특정 기능 사용을 위한 개인 권한 신청이 필요한 상황",
            "keywords": ["개인권한신청", "서비스수행", "처리권한", "업무팀", "CS지원팀", "권한신청"],
            "symptoms": [
                "서비스 수행 처리 권한이 없음",
                "특정 기능에 접근할 수 없음",
                "권한 신청 방법을 모르겠음",
                "기존 업무팀에서 권한 변경이 필요함"
            ],
            "questions_to_ask": [
                "어떤 권한이 필요하신가요? (서비스수행, 처리권한 등)",
                "현재 소속된 업무팀이 있나요?",
                "이전에 해당 권한을 사용한 적이 있나요?",
                "긴급하게 필요한 업무인가요?"
            ],
            "solution_steps": [
                "1. 기존 업무팀이 있다면 먼저 삭제 처리합니다",
                "2. CS지원팀으로 업무팀을 변경합니다",
                "3. 필요한 개인 권한을 신청합니다",
                "4. 승인 완료 후 권한 사용이 가능합니다"
            ],
            "escalation_triggers": [
                "권한 승인이 지연되는 경우",
                "업무팀 변경이 안 되는 경우",
                "긴급 업무로 즉시 권한이 필요한 경우"
            ],
            "search_content": "OSS 권한 신청 개인 권한 신청 개인권한신청 서비스수행 처리권한 업무팀 CS지원팀 권한신청 OSS에서 서비스 수행 처리나 특정 기능 사용을 위한 개인 권한 신청이 필요한 상황"
        },
        {
            "id": "oss_permission_team_application",
            "issue_type": "oss_permission_request",
            "issue_name": "OSS 권한 신청",
            "case_type": "team_application",
            "case_name": "업무팀 신청",
            "description": "OSS에서 업무 수행을 위해 특정 업무팀에 가입 신청이 필요한 상황",
            "keywords": ["업무팀신청", "KT NETCORE", "업무팀조회", "팀가입", "업무팀"],
            "symptoms": [
                "업무팀 신청 방법을 모르겠음",
                "적절한 업무팀을 찾을 수 없음",
                "업무팀 가입이 필요함",
                "기존 업무팀에서 변경이 필요함"
            ],
            "questions_to_ask": [
                "어떤 업무를 수행하시나요?",
                "소속 부서나 담당 업무 영역이 어떻게 되시나요?",
                "이전에 업무팀에 가입한 적이 있나요?",
                "특정 업무팀을 염두에 두고 계신가요?"
            ],
            "solution_steps": [
                "1. OSS 업무팀 조회 화면에 접속합니다",
                "2. 'KT NETCORE'로 검색합니다",
                "3. 적합한 업무팀을 선택합니다",
                "4. 업무팀 가입을 신청합니다",
                "5. 승인 완료를 기다립니다"
            ],
            "escalation_triggers": [
                "적절한 업무팀을 찾을 수 없는 경우",
                "업무팀 가입 승인이 지연되는 경우",
                "업무팀 변경이 복잡한 경우"
            ],
            "search_content": "OSS 권한 신청 업무팀 신청 업무팀신청 KT NETCORE 업무팀조회 팀가입 업무팀 OSS에서 업무 수행을 위해 특정 업무팀에 가입 신청이 필요한 상황"
        },
        {
            "id": "oss_permission_personal_info_access",
            "issue_type": "oss_permission_request",
            "issue_name": "OSS 권한 신청",
            "case_type": "personal_info_access",
            "case_name": "개인정보 숨김해제 권한",
            "description": "OSS에서 개인정보 조회를 위한 숨김해제 권한 신청 및 2차 승인자 관련 문의",
            "keywords": ["개인정보권한", "숨김해제권한", "2차승인자", "2차결재자", "기관보안담당자"],
            "symptoms": [
                "개인정보 숨김해제 권한이 필요함",
                "2차 결재자 정보를 찾을 수 없다는 메시지",
                "2차 승인자가 누구인지 모르겠음",
                "개인정보 권한 신청 방법을 모르겠음"
            ],
            "questions_to_ask": [
                "개인정보 조회가 업무상 필요한가요?",
                "소속 조직의 상위 기관을 알고 계신가요?",
                "이전에 개인정보 권한을 신청한 적이 있나요?",
                "2차 승인자에 대한 안내를 받으신 적이 있나요?"
            ],
            "solution_steps": [
                "1. 개인정보 숨김해제 권한을 신청합니다",
                "2. 2차 승인자는 KT담당자 소속 조직의 상위 기관보안담당자입니다",
                "3. 해당 담당자에게 승인 요청을 합니다",
                "4. 승인 완료 후 개인정보 조회가 가능합니다"
            ],
            "escalation_triggers": [
                "2차 승인자를 찾을 수 없는 경우",
                "기관보안담당자 승인이 지연되는 경우",
                "긴급 업무로 개인정보 조회가 필요한 경우"
            ],
            "search_content": "OSS 권한 신청 개인정보 숨김해제 권한 개인정보권한 숨김해제권한 2차승인자 2차결재자 기관보안담당자 OSS에서 개인정보 조회를 위한 숨김해제 권한 신청 및 2차 승인자 관련 문의"
        },
        {
            "id": "oss_user_info_management",
            "issue_type": "oss_information_management",
            "issue_name": "OSS 정보 관리",
            "case_type": "user_info_sync",
            "case_name": "사용자 정보 동기화",
            "description": "IDMS나 인사시스템에서 변경된 정보가 OSS에 반영되지 않거나 동기화 관련 문의",
            "keywords": ["사용자정보관리", "IDMS", "인사시스템", "정보반영", "동기화", "KT담당자변경"],
            "symptoms": [
                "IDMS에서 정보 변경했는데 OSS에 반영 안 됨",
                "인사시스템 변경사항이 OSS에 업데이트 안 됨",
                "담당자 정보가 예전 것으로 나옴",
                "핸드폰 번호나 이메일이 업데이트 안 됨"
            ],
            "questions_to_ask": [
                "언제 정보를 변경하셨나요?",
                "어떤 정보를 변경하셨나요? (담당자, 연락처, 부서 등)",
                "IDMS와 인사시스템 중 어디서 변경하셨나요?",
                "변경 후 며칠이 지났나요?"
            ],
            "solution_steps": [
                "1. IDMS나 인사시스템에서 정보 변경을 확인합니다",
                "2. 일반적으로 익일 OSS에 자동 반영됩니다",
                "3. 2-3일 후에도 반영되지 않으면 시스템 관리자에게 문의합니다",
                "4. 긴급한 경우 수동 동기화를 요청할 수 있습니다"
            ],
            "escalation_triggers": [
                "3일 이상 정보가 반영되지 않는 경우",
                "중요한 업무에 영향을 주는 경우",
                "시스템 오류로 의심되는 경우"
            ],
            "search_content": "OSS 정보 관리 사용자 정보 동기화 사용자정보관리 IDMS 인사시스템 정보반영 동기화 KT담당자변경 IDMS나 인사시스템에서 변경된 정보가 OSS에 반영되지 않거나 동기화 관련 문의"
        },
        {
            "id": "oss_login_browser_issue",
            "issue_type": "oss_login_failure",
            "issue_name": "OSS 로그인 문제",
            "case_type": "browser_environment",
            "case_name": "인터넷 환경 설정 문제",
            "description": "브라우저나 인터넷 환경 설정으로 인해 OSS 로그인이 안 되거나 반응이 없는 상황",
            "keywords": ["인터넷환경설정", "브라우저", "크롬", "로그인반응없음", "화면공유", "데스크탑공유"],
            "symptoms": [
                "아이디와 비밀번호 입력 시 반응 없음",
                "로그인 버튼을 눌러도 아무 일이 일어나지 않음",
                "특정 브라우저에서만 문제 발생",
                "오류 메시지 없이 로그인이 안 됨"
            ],
            "questions_to_ask": [
                "어떤 브라우저를 사용하고 계신가요?",
                "다른 브라우저로도 시도해보셨나요?",
                "팝업 차단이나 보안 설정이 있나요?",
                "회사 네트워크에서 접속하고 계신가요?"
            ],
            "solution_steps": [
                "1. 크롬 브라우저 사용을 권장합니다",
                "2. 브라우저 캐시와 쿠키를 삭제합니다",
                "3. 팝업 차단 설정을 해제합니다",
                "4. 방화벽이나 보안 프로그램 설정을 확인합니다",
                "5. 필요시 화면 공유를 통한 원격 지원을 받습니다"
            ],
            "escalation_triggers": [
                "브라우저 설정 변경으로도 해결되지 않는 경우",
                "네트워크나 보안 정책 문제인 경우",
                "화면 공유 지원이 필요한 경우"
            ],
            "search_content": "OSS 로그인 문제 인터넷 환경 설정 문제 인터넷환경설정 브라우저 크롬 로그인반응없음 화면공유 데스크탑공유 브라우저나 인터넷 환경 설정으로 인해 OSS 로그인이 안 되거나 반응이 없는 상황"
        }
    ]
    
    print(f"📚 Loaded {len(knowledge_base)} knowledge base entries")
    return knowledge_base

def upload_knowledge_base():
    """Upload knowledge base to Azure AI Search"""
    
    print("📤 Uploading knowledge base to Azure AI Search...")
    
    # Initialize search client
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    # Load knowledge base
    documents = load_knowledge_base()
    
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

def test_search():
    """Test the search functionality"""
    
    print("🧪 Testing search functionality...")
    
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    # Test queries
    test_queries = [
        "OSS 로그인이 안 돼요",
        "비밀번호를 잊어버렸어요",
        "권한이 필요해요",
        "업무팀 가입하고 싶어요"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        
        try:
            results = search_client.search(
                search_text=query,
                top=3,
                include_total_results=True,
                search_fields=["case_name", "description", "symptoms", "search_content"],
                select=["id", "case_name", "description"]
            )
            
            print(f"   Found {results.get_count()} total results:")
            for i, result in enumerate(results, 1):
                score = result.get('@search.score', 0)
                print(f"   {i}. {result['case_name']} (Score: {score:.2f})")
                print(f"      {result['description'][:100]}...")
                
        except Exception as e:
            print(f"   ❌ Search error: {e}")

def main():
    """Main execution function"""
    
    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        print("❌ Missing Azure Search configuration!")
        print("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY environment variables")
        return False
    
    print("🚀 Setting up Azure AI Search for RAG...")
    print(f"   Endpoint: {SEARCH_ENDPOINT}")
    print(f"   Index: {INDEX_NAME}")
    
    # Step 1: Create index
    if not create_search_index():
        return False
    
    # Step 2: Upload knowledge base
    if not upload_knowledge_base():
        return False
    
    # Step 3: Test search
    test_search()
    
    print("\n🎉 Azure AI Search setup completed successfully!")
    print("Your Flask app can now use RAG functionality!")
    
    return True

if __name__ == "__main__":
    main()