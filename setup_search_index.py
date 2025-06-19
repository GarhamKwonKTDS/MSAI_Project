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

# Knowledge base file path
KNOWLEDGE_BASE_FILE = os.getenv('KNOWLEDGE_BASE_FILE', 'knowledge_base.json')

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
        
        # Array fields
        SearchField(
            name="keywords",
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
        
        # New field for conditions (stored as JSON string for complex object)
        SearchableField(name="conditions_json", type=SearchFieldDataType.String),
        
        # Vector field for embeddings
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
    
    # Create the index
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
    """Load knowledge base data from JSON file"""
    
    try:
        with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
            knowledge_base = json.load(f)
        print(f"📚 Loaded {len(knowledge_base)} knowledge base entries from {KNOWLEDGE_BASE_FILE}")
        return knowledge_base
    except FileNotFoundError:
        print(f"❌ Knowledge base file not found: {KNOWLEDGE_BASE_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing knowledge base JSON: {e}")
        return []
    except Exception as e:
        print(f"❌ Error loading knowledge base: {e}")
        return []

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
    
    if not documents:
        print("❌ No documents to upload")
        return False
    
    # Process documents for upload
    processed_documents = []
    
    for doc in documents:
        # Create a copy to avoid modifying the original
        processed_doc = doc.copy()
        
        # Convert conditions dict to JSON string for storage
        if 'conditions' in processed_doc:
            processed_doc['conditions_json'] = json.dumps(processed_doc['conditions'], ensure_ascii=False)
            # Remove the original conditions field as it's not in our schema
            del processed_doc['conditions']
        
        # Create combined text for embedding
        conditions_text = ""
        if 'conditions_json' in processed_doc:
            conditions_dict = json.loads(processed_doc['conditions_json'])
            conditions_text = " ".join(conditions_dict.values())
        
        embedding_text = f"{processed_doc['case_name']} {processed_doc['description']} {conditions_text} {processed_doc['search_content']}"
        
        # Generate embedding
        print(f"🔄 Generating embedding for: {processed_doc['id']}")
        embedding = generate_embeddings(embedding_text)
        
        if embedding:
            processed_doc['content_vector'] = embedding
            processed_documents.append(processed_doc)
        else:
            print(f"⚠️ Failed to generate embedding for {processed_doc['id']}")
    
    try:
        # Upload documents
        result = search_client.upload_documents(documents=processed_documents)
        
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
        "권한이 필요해요",
        "9사번이 필요해요"
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
                select=["id", "case_name", "description", "conditions_json"]
            )
            
            print(f"   Hybrid search results:")
            for i, result in enumerate(results, 1):
                score = result.get('@search.score', 0)
                reranker_score = result.get('@search.reranker_score', 0)
                print(f"   {i}. {result['case_name']} (Score: {score:.2f}, Semantic: {reranker_score:.2f})")
                print(f"      {result['description'][:100]}...")
                
                # Show conditions
                if 'conditions_json' in result:
                    conditions = json.loads(result['conditions_json'])
                    print(f"      Conditions: {len(conditions)} defined")
                
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
    print(f"   Knowledge Base File: {KNOWLEDGE_BASE_FILE}")
    
    # Step 1: Create index with vector and semantic capabilities
    if not create_search_index():
        return False
    
    # Step 2: Upload knowledge base with embeddings
    if not upload_knowledge_base_with_embeddings():
        return False
    
    # Step 3: Test hybrid search
    test_hybrid_search()
    
    print("\n🎉 Azure AI Search with hybrid search setup completed successfully!")
    print("Your Flask app can now use vector + semantic search with the new conditions structure!")
    
    return True

if __name__ == "__main__":
    main()