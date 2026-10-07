import sys
import uuid
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, BackgroundTasks, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

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
        graph = build_taxonomy_graph()
        init_trace(run_id, patent_ids)
        
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
