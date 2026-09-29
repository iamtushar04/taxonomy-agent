import uuid
import os
from taxonomy_builder.graph import build_taxonomy_graph
from taxonomy_builder.utils.tracer import init_trace

def run():
    print("Initializing Taxonomy Builder Graph...")
    graph = build_taxonomy_graph()
    
    # The real patents provided by user
    patent_ids = [
        "US11559349B2", "US12285260B2", "US12150751B2", "US12016623B2"
       
    ]
    
    run_id = str(uuid.uuid4())[:8]
    init_trace(run_id, patent_ids)
    
    print(f"\n--- Starting Execution (Trace ID: {run_id}) ---")
    
    initial_state = {
        "run_id": run_id,
        "patent_ids": patent_ids,
        "all_concepts": [],
        "errors": []
    }
    
    # Increase recursion limit just in case graph needs it
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 50}
    final_state = graph.invoke(initial_state, config=config)
    
    print(f"\n--- Execution Complete (See logs/traces/taxonomy_run_{run_id}_trace.md) ---")
    print(f"Total extracted concepts: {len(final_state.get('all_concepts', []))}")
    print(f"Final Taxonomy Nodes Count: {len(final_state.get('final_taxonomy', []))}")

if __name__ == "__main__":
    # Change CWD to the parent directory to ensure relative paths for data folder work nicely
    # or rely on absolute paths in format_taxonomy.py
    run()
