import uuid
import os
from taxonomy_builder.graph import build_taxonomy_graph
from taxonomy_builder.utils.tracer import init_trace

def run():
    print("Initializing Taxonomy Builder Graph...")
    graph = build_taxonomy_graph()
    
    # The real patents provided by user
    patent_ids = [
        # "US20170349734A1", "US11691998B2", "US9902845B2", "US9156929B2",
        # "US11472949B2", "US10005858B2", "US10400048B2", "US10513569B2",
        # "US6617277B2", "US10494454B2", "US20220049797A1", "US7919569B2",
        # "US20040038806A1", "US8674026B2", "US20220363787A1", "US20240343842A1",
        # "US6207746B1", "JP3901032B2", "JP2003268331A", "JP2017145303A",
        # "US9714306B2", "JP2002080507A", "JP2023131454A", "JP2011108655A",
        # "JP2009013429A", "JP2005133021A", "JP2005075895A", "JP4231367B2",
        # "JP4231356B2", "JP2003192803A", "US6861153B2", "JP2002029009A",
        # "JP4146013B2"
        # "EP3350236B1", "US10611867B2", "US10308736B2", "US6419966B1", "CN111491959B"
        "US20250031769A1",
        "CN120477432A",
        "US20250241379A1",
        "US12310417B2",
        "US20250212969A1",
        "CN116782784A"
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
