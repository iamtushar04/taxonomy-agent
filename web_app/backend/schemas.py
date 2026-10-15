from typing import List, Optional
from pydantic import BaseModel

class PatentRequest(BaseModel):
    run_id: Optional[str] = None
    patent_ids: List[str]
    session_upload_id: Optional[str] = None
    product_urls: Optional[List[str]] = None
    mental_model_context: Optional[str] = None
    instructions: Optional[str] = None
    messages: Optional[List[dict]] = None
    mental_model: Optional[dict] = None

class GraphEdge(BaseModel):
    source: str
    target: str

class GraphNodeData(BaseModel):
    label: str
    contexts_by_patent: Optional[dict[str, list[str]]] = None
    contexts_by_pmid: Optional[dict[str, list[str]]] = None
    contexts_by_product: Optional[dict[str, list[str]]] = None
    patent_contexts: Optional[list[str]] = None
    isExpanded: Optional[bool] = None
    supporting_patent_ids: Optional[list[str]] = None
    supporting_pmids: Optional[list[str]] = None
    supporting_product_ids: Optional[list[str]] = None

class GraphNode(BaseModel):
    id: str
    data: GraphNodeData

class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

class RenameRunRequest(BaseModel):
    name: str

class DeleteSessionResponse(BaseModel):
    status: str = "accepted"
    message: str
    session_id: str
