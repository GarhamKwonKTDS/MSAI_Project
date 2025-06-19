# admin_backend/services/azure_search.py

import os
import logging
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)

class AzureSearchService:
    """Azure Search service for admin operations"""
    
    def __init__(self):
        self.endpoint = os.getenv('AZURE_SEARCH_ENDPOINT')
        self.key = os.getenv('AZURE_SEARCH_KEY')
        self.index_name = os.getenv('AZURE_SEARCH_INDEX', 'oss-knowledge-base')
        
        if not self.endpoint or not self.key:
            logger.warning("Azure Search credentials not found")
            self.client = None
            return
            
        try:
            self.client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=AzureKeyCredential(self.key)
            )
            logger.info(f"✅ Azure Search initialized: {self.index_name}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Azure Search: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if search service is available"""
        return self.client is not None
    
    def search_cases(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for cases"""
        if not self.client:
            return []
            
        try:
            results = self.client.search(
                search_text=query,
                top=top_k,
                select=["id", "issue_type", "issue_name", "case_type", "case_name", "description"]
            )
            
            cases = []
            for result in results:
                cases.append(dict(result))
            
            logger.info(f"Found {len(cases)} cases for query: '{query[:50]}...'")
            return cases
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific case by ID"""
        if not self.client:
            return None
            
        try:
            result = self.client.get_document(key=case_id)
            return dict(result)
        except Exception as e:
            logger.error(f"Error getting case {case_id}: {e}")
            return None
    
    def create_case(self, case_data: Dict[str, Any]) -> bool:
        """Create a new case"""
        if not self.client:
            return False
            
        try:
            result = self.client.upload_documents(documents=[case_data])
            return result[0].succeeded
        except Exception as e:
            logger.error(f"Error creating case: {e}")
            return False
    
    def update_case(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        """Update an existing case"""
        if not self.client:
            return False
            
        try:
            case_data["id"] = case_id
            result = self.client.merge_or_upload_documents(documents=[case_data])
            return result[0].succeeded
        except Exception as e:
            logger.error(f"Error updating case: {e}")
            return False
    
    def delete_case(self, case_id: str) -> bool:
        """Delete a case"""
        if not self.client:
            return False
            
        try:
            result = self.client.delete_documents(documents=[{"id": case_id}])
            return result[0].succeeded
        except Exception as e:
            logger.error(f"Error deleting case: {e}")
            return False