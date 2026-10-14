from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ProductFeature(BaseModel):
    name: str
    description: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None

class ParsedProduct(BaseModel):
    product_id: str
    product_name: str
    brand_or_assignee: Optional[str] = "Unknown"
    category: Optional[str] = "Uncategorized"
    features: List[str] = []
    full_text_snippet: Optional[str] = ""
    source_filename: str

class ProductUploadResponse(BaseModel):
    session_upload_id: str
    total_files_parsed: int
    total_products_extracted: int
    products: List[ParsedProduct]
    errors: Optional[List[str]] = []

class ProductMappingRequest(BaseModel):
    run_id: str
    session_upload_id: Optional[str] = None
    products: Optional[List[ParsedProduct]] = None

class ProductNodeMapping(BaseModel):
    node_id: str
    node_name: str
    supporting_product_ids: List[str]
    overlap_evidence: Dict[str, str] = {}
