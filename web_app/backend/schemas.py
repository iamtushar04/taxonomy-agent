from typing import List, Optional
from pydantic import BaseModel

class PatentRequest(BaseModel):
    patent_ids: List[str]

class GraphEdge(BaseModel):
    source: str
    target: str

class GraphNodeData(BaseModel):
    label: str
    contexts_by_patent: Optional[dict[str, list[str]]] = None
    contexts_by_pmid: Optional[dict[str, list[str]]] = None
    patent_contexts: Optional[list[str]] = None
    isExpanded: Optional[bool] = None
    supporting_patent_ids: Optional[list[str]] = None
    supporting_pmids: Optional[list[str]] = None

class GraphNode(BaseModel):
    id: str
    data: GraphNodeData

class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
