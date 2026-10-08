import sys
import uuid
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, BackgroundTasks, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

import os
# Add the parent folder to the Python path so it can find taxonomy_builder
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from taxonomy_builder.graph import build_taxonomy_graph
from taxonomy_builder.utils.tracer import init_trace

app = FastAPI(title="Taxonomy Builder API")

# Allow the React frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks_db: Dict[str, dict] = {}

class PatentRequest(BaseModel):
    patent_ids: List[str]

def run_taxonomy_pipeline(run_id: str, patent_ids: List[str]):
    try:
        tasks_db[run_id]["status"] = "running"
        
        # Clean up IDs: Users might paste "12345 67890" without commas
        cleaned_ids = []
        for raw_id in patent_ids:
            cleaned_ids.extend([part.strip() for part in raw_id.replace(',', ' ').split() if part.strip()])
        patent_ids = cleaned_ids

        init_trace(run_id, patent_ids)
        
        is_pubmed = all(pid.isdigit() for pid in patent_ids)
        
        if is_pubmed:
            from taxonomy_builder.pubmed_graph import build_pubmed_graph
            graph = build_pubmed_graph()
            initial_state = {
                "run_id": run_id,
                "pmids": patent_ids,
                "all_concepts": [],
                "errors": []
            }
        else:
            from taxonomy_builder.graph import build_taxonomy_graph
            graph = build_taxonomy_graph()
            initial_state = {
                "run_id": run_id,
                "patent_ids": patent_ids,
                "all_concepts": [],
                "errors": []
            }
            
        config = {"configurable": {"thread_id": run_id}, "recursion_limit": 50}
        
        final_state = graph.invoke(initial_state, config=config)
        
        tasks_db[run_id]["status"] = "completed"
        tasks_db[run_id]["result"] = final_state.get("final_taxonomy", [])
        tasks_db[run_id]["source_data"] = final_state.get("pubmed_data", final_state.get("patents_data", {}))
        tasks_db[run_id]["is_pubmed"] = is_pubmed
    except Exception as e:
        tasks_db[run_id]["status"] = "failed"
        tasks_db[run_id]["error"] = str(e)

@app.post("/api/build-taxonomy")
async def build_taxonomy(request: PatentRequest, background_tasks: BackgroundTasks):
    if not request.patent_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one patent ID.")
    run_id = str(uuid.uuid4())[:8]
    tasks_db[run_id] = {"status": "pending", "patent_ids": request.patent_ids}
    background_tasks.add_task(run_taxonomy_pipeline, run_id, request.patent_ids)
    return {"run_id": run_id, "message": "Started"}

@app.get("/api/status/{run_id}")
async def get_status(run_id: str):
    if run_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Not found.")
    info = tasks_db[run_id]
    resp = {"run_id": run_id, "status": info["status"]}
    if info["status"] == "failed":
        resp["error"] = info.get("error")
    return resp

@app.get("/api/taxonomy/{run_id}")
async def get_taxonomy(run_id: str):
    if run_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Not found.")
    info = tasks_db[run_id]
    if info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Not ready.")
    return {"run_id": run_id, "taxonomy": info.get("result", [])}

from pydantic import BaseModel
from typing import Optional

class GraphEdge(BaseModel):
    source: str
    target: str

class GraphNodeData(BaseModel):
    label: str
    contexts_by_patent: Optional[dict[str, list[str]]] = None
    contexts_by_pmid: Optional[dict[str, list[str]]] = None
    patent_contexts: Optional[list[str]] = None
    isExpanded: Optional[bool] = None

class GraphNode(BaseModel):
    id: str
    data: GraphNodeData

class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

@app.post("/api/download-excel/{run_id}")
async def download_excel(run_id: str, payload: GraphPayload):
    import os
    # pyrefly: ignore [missing-import]
    from fastapi.responses import FileResponse
    
    if run_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Run ID not found.")
        
    is_pubmed = tasks_db[run_id].get("is_pubmed", False)
    source_data = tasks_db[run_id].get("source_data", {})
    
    # Rebuild flat taxonomy from payload
    parent_map = {e.target: e.source for e in payload.edges}
    flat_nodes = []
    
    for n in payload.nodes:
        pmids = set(n.data.contexts_by_pmid.keys()) if n.data.contexts_by_pmid else set()
        patents = set(n.data.contexts_by_patent.keys()) if n.data.contexts_by_patent else set()
        
        flat_nodes.append({
            "node_id": n.id,
            "parent_node_id": parent_map.get(n.id),
            "name": n.data.label,
            "level": 0, 
            "description": "",
            "supporting_pmids": list(pmids),
            "supporting_patent_ids": list(patents),
            "contexts_by_pmid": n.data.contexts_by_pmid or {},
            "contexts_by_patent": n.data.contexts_by_patent or {}
        })
        
    # Bubble up patents
    children_map = {}
    for n in flat_nodes:
        if n["parent_node_id"]:
            children_map.setdefault(n["parent_node_id"], []).append(n["node_id"])
            
    node_map = {n["node_id"]: n for n in flat_nodes}
    
    def collect_descendants(node_id, visited):
        if node_id in visited: return set(), set()
        visited.add(node_id)
        res_pmid = set(node_map[node_id].get("supporting_pmids", []))
        res_pat = set(node_map[node_id].get("supporting_patent_ids", []))
        for child in children_map.get(node_id, []):
            cp, ct = collect_descendants(child, visited)
            res_pmid.update(cp)
            res_pat.update(ct)
        return res_pmid, res_pat
        
    for n in flat_nodes:
        p1, p2 = collect_descendants(n["node_id"], set())
        n["supporting_pmids"] = sorted(list(p1))
        n["supporting_patent_ids"] = sorted(list(p2))
        
    # Rebuild nested tree
    roots = [n for n in flat_nodes if not n["parent_node_id"]]
    def _build(node_id):
        children = [n for n in flat_nodes if n["parent_node_id"] == node_id]
        if not children: return {}
        return {c["name"]: _build(c["node_id"]) for c in children}
        
    enriched_tree = {root["name"]: _build(root["node_id"]) for root in roots}
    
    matrix_path = os.path.join(parent_dir, "data", f"taxonomy_matrix_{run_id}.xlsx")
    
    if is_pubmed:
        from taxonomy_builder.utils.pubmed_excel_matrix_generator import generate_pubmed_matrix_excel
        generate_pubmed_matrix_excel(source_data, flat_nodes, enriched_tree, matrix_path)
    else:
        from taxonomy_builder.utils.excel_matrix_generator import generate_dynamic_matrix_excel
        generate_dynamic_matrix_excel(source_data, flat_nodes, enriched_tree, matrix_path)
        
    if not os.path.exists(matrix_path):
        raise HTTPException(status_code=404, detail="Excel file generation failed.")
        
    return FileResponse(
        path=matrix_path, 
        filename=f"Taxonomy_Matrix_{run_id}.xlsx", 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
