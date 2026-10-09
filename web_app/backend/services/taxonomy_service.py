import sys
import os
from typing import List
# pyrefly: ignore [missing-import]
from fastapi import HTTPException

# Add the parent folder to the Python path so it can find taxonomy_builder
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# pyrefly: ignore [missing-import]
import models
# pyrefly: ignore [missing-import]
from database import SessionLocal
# pyrefly: ignore [missing-import]
from services import db_service
from taxonomy_builder.utils.tracer import init_trace

def run_taxonomy_pipeline(run_id: str, patent_ids: List[str]):
    try:
        db = SessionLocal()
        db_service.update_run_status_running(db, run_id)
            
        # VERY IMPORTANT FOR 1,000 PATENTS: Close the DB connection BEFORE the 5 hour run!
        # Otherwise PostgreSQL will kill the idle connection and the save will fail!
        db.close()
            
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
            
        # INCREASED RECURSION LIMIT FOR 1,000 PATENTS
        config = {"configurable": {"thread_id": run_id}, "recursion_limit": 2000}
        final_state = graph.invoke(initial_state, config=config)
        
        # Open a completely fresh connection to save the results
        db = SessionLocal()
        
        final_taxonomy = final_state.get("final_taxonomy", [])
        source_data = final_state.get("pubmed_data", final_state.get("patents_data", {}))
        
        # Generate meaningful name
        meaningful_name = None
        if final_taxonomy:
            roots = [n for n in final_taxonomy if not n.get("parent_node_id")]
            if len(roots) > 1:
                meaningful_name = " & ".join([r.get("name", "") for r in roots[:2]]) + " Taxonomy"
            elif len(roots) == 1:
                root = roots[0]
                root_name = root.get("name", "")
                children = [n for n in final_taxonomy if n.get("parent_node_id") == root.get("node_id")]
                generic_roots = {"technology", "technologies", "innovation", "innovations", "patent", "patents", "invention", "inventions", "concept", "concepts"}
                
                if not children:
                    meaningful_name = f"{root_name} Taxonomy"
                else:
                    child_names = [c.get("name", "") for c in children[:2]]
                    if root_name.lower() in generic_roots:
                        meaningful_name = " & ".join(child_names) + " Taxonomy"
                    else:
                        meaningful_name = " & ".join(child_names) + f" ({root_name})"
        
        db_service.update_run_status_completed(db, run_id, final_taxonomy, source_data, is_pubmed, meaningful_name)
    except Exception as e:
        db_service.update_run_status_failed(db, run_id, str(e))
    finally:
        db.close()


def process_excel_generation(run_id: str, payload, run_record):
    is_pubmed = run_record.is_pubmed
    source_data = run_record.source_data or {}
    
    parent_map = {e.target: e.source for e in payload.edges}
    flat_nodes = []
    
    for n in payload.nodes:
        pmids = set(n.data.supporting_pmids) if n.data.supporting_pmids else set()
        if not pmids and n.data.contexts_by_pmid:
            pmids = set(n.data.contexts_by_pmid.keys())
            
        patents = set(n.data.supporting_patent_ids) if n.data.supporting_patent_ids else set()
        if not patents and n.data.contexts_by_patent:
            patents = set(n.data.contexts_by_patent.keys())
        
        flat_nodes.append({
            "node_id": n.id,
            "parent_node_id": parent_map.get(n.id),
            "name": n.data.label,
            "level": 0, 
            "description": "",
            "supporting_pmids": list(pmids),
            "supporting_patent_ids": list(patents),
            "contexts_by_patent": n.data.contexts_by_patent or {},
            "contexts_by_pmid": n.data.contexts_by_pmid or {}
        })
        
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
        
    roots = [n for n in flat_nodes if not n["parent_node_id"]]
    def _build(node_id):
        children = [n for n in flat_nodes if n["parent_node_id"] == node_id]
        if not children: return {}
        return {c["name"]: _build(c["node_id"]) for c in children}
        
    enriched_tree = {root["name"]: _build(root["node_id"]) for root in roots}
    
    matrix_path = os.path.join(parent_dir, "data", f"taxonomy_matrix_{run_id}.xlsx")
    
    # Clean up input_ids in case they were pasted with spaces instead of commas
    cleaned_input_ids = []
    if run_record.input_ids:
        for raw_id in run_record.input_ids:
            cleaned_input_ids.extend([part.strip() for part in raw_id.replace(',', ' ').split() if part.strip()])
    else:
        cleaned_input_ids = None

    if is_pubmed:
        from taxonomy_builder.utils.pubmed_excel_matrix_generator import generate_pubmed_matrix_excel
        generate_pubmed_matrix_excel(source_data, flat_nodes, enriched_tree, matrix_path, cleaned_input_ids)
    else:
        from taxonomy_builder.utils.excel_matrix_generator import generate_dynamic_matrix_excel
        generate_dynamic_matrix_excel(source_data, flat_nodes, enriched_tree, matrix_path, cleaned_input_ids)
        
    if not os.path.exists(matrix_path):
        raise HTTPException(status_code=404, detail="Excel file generation failed.")
        
    return matrix_path
