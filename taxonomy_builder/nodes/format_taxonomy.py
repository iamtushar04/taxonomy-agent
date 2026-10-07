import json
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from taxonomy_builder.state import TaxonomyGenerationState
from taxonomy_builder.utils.excel_matrix_generator import generate_dynamic_matrix_excel

def generate_excel_template(draft_tree: dict, output_path: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Taxonomy Template"

    # Fixed Metadata Columns
    fixed_headers = ["S.No", "Patent Number", "Patent Title", "Assignee", "Summary"]
    
    # Styling
    fixed_header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid") # Dark Red
    fixed_header_font = Font(bold=True, color="FFFFFF") # White Text
    
    dynamic_header_font = Font(bold=True, color="000000") # Black Text
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Vibrant palette for the taxonomy branches (Green, Blue, Orange, Purple, Yellow, Aqua, Light Green, Peach)
    palette = ["92D050", "00B0F0", "FFC000", "B1A0C7", "FFFF00", "B7DEE8", "D9E1F2", "FCE4D6"]

    # Write fixed headers to Row 2 (as in Fresh_Test)
    for col_idx, header in enumerate(fixed_headers, start=1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = fixed_header_font
        cell.fill = fixed_header_fill
        cell.alignment = center_align
        ws.merge_cells(start_row=2, start_column=col_idx, end_row=4, end_column=col_idx)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 20

    current_col = len(fixed_headers) + 1

    def write_tree_headers(tree_dict, row, start_col, color_idx=0):
        """
        Recursively writes headers and merges parent cells.
        Returns the number of leaf columns this branch spans.
        """
        if not tree_dict:
            return 1 # A leaf node takes exactly 1 column
            
        total_span = 0
        for i, (node_name, children) in enumerate(tree_dict.items()):
            # If at the root level, rotate through the palette. Otherwise inherit the parent's color.
            current_color_idx = (color_idx + i) % len(palette) if row == 2 else color_idx
            fill_color = palette[current_color_idx]
            
            child_span = write_tree_headers(children, row + 1, start_col + total_span, current_color_idx)
            
            # Write the current node name
            cell = ws.cell(row=row, column=start_col + total_span, value=node_name)
            cell.font = dynamic_header_font
            cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
            cell.alignment = center_align
            
            # Merge if this node spans multiple children
            if child_span > 1:
                ws.merge_cells(
                    start_row=row, 
                    start_column=start_col + total_span, 
                    end_row=row, 
                    end_column=start_col + total_span + child_span - 1
                )
                
            total_span += child_span
            
        return total_span

    # Write the dynamic taxonomy starting at row 2 and the next available column
    write_tree_headers(draft_tree, row=2, start_col=current_col)
    
    # Auto-adjust column widths for the taxonomy columns
    max_col = ws.max_column
    for col_idx in range(len(fixed_headers) + 1, max_col + 1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 25

    wb.save(output_path)


def generate_html_graph(draft_tree: dict, output_path: str):
    def dict_to_echarts_tree(tree_dict):
        children = []
        for k, v in tree_dict.items():
            node = {"name": k}
            if isinstance(v, dict) and v:
                node["children"] = dict_to_echarts_tree(v)
            else:
                node["value"] = 1
            children.append(node)
        return children

    if "Technology" in draft_tree and len(draft_tree) == 1:
        echarts_data = {"name": "Technology", "children": dict_to_echarts_tree(draft_tree["Technology"])}
    else:
        echarts_data = {"name": "Taxonomy Root", "children": dict_to_echarts_tree(draft_tree)}

    html_content = f"""
    <!DOCTYPE html>
    <html style="height: 100%">
    <head>
        <meta charset="utf-8">
        <title>Taxonomy Interactive Graph</title>
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    </head>
    <body style="height: 100%; margin: 0">
        <div id="container" style="height: 100%"></div>
        <script type="text/javascript">
            var dom = document.getElementById('container');
            var myChart = echarts.init(dom, null, {{
              renderer: 'canvas',
              useDirtyRect: false
            }});
            var data = {json.dumps(echarts_data)};
            var option = {{
              tooltip: {{ trigger: 'item', triggerOn: 'mousemove' }},
              series: [
                {{
                  type: 'tree',
                  data: [data],
                  top: '1%',
                  left: '10%',
                  bottom: '1%',
                  right: '20%',
                  symbolSize: 10,
                  label: {{
                    position: 'left',
                    verticalAlign: 'middle',
                    align: 'right',
                    fontSize: 14,
                    fontWeight: 'bold'
                  }},
                  leaves: {{
                    label: {{
                      position: 'right',
                      verticalAlign: 'middle',
                      align: 'left',
                      fontWeight: 'normal'
                    }}
                  }},
                  emphasis: {{ focus: 'descendant' }},
                  expandAndCollapse: true,
                  animationDuration: 550,
                  animationDurationUpdate: 750,
                  initialTreeDepth: 3
                }}
              ]
            }};
            myChart.setOption(option);
            window.addEventListener('resize', myChart.resize);
        </script>
    </body>
    </html>
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def format_taxonomy(state: TaxonomyGenerationState) -> dict:
    """
    Finalizes the taxonomy array, dumps it to a JSON file, 
    generates an Excel template, and generates an interactive HTML graph.
    """
    print("--- FORMATTING TAXONOMY ---")
    final_taxonomy = state.get("final_taxonomy", [])
    draft_tree = state.get("draft_tree", {})
    run_id = state.get("run_id", "default")
    
    # 1. Write the JSON to data/
    json_path = r"c:\Users\Vipul\Desktop\taxonomies_agent\data\draft_taxonomy.json"
    with open(json_path, "w") as f:
        json.dump(final_taxonomy, f, indent=2)
    print(f"-> Wrote final taxonomy to {json_path}")
    
    # 2. Write the Excel Template to data/
    excel_path = f"c:\\Users\\Vipul\\Desktop\\taxonomies_agent\\data\\taxonomy_template_{run_id}.xlsx"
    try:
        generate_excel_template(draft_tree, excel_path)
        print(f"-> Generated multi-level Excel template at {excel_path}")
    except Exception as e:
        print(f"Failed to generate Excel template: {e}")

    # 2.5 Write the Dynamic Matrix Excel (Rows = Patents, Cols = Taxonomy Nodes)
    matrix_path = f"c:\\Users\\Vipul\\Desktop\\taxonomies_agent\\data\\taxonomy_matrix_{run_id}.xlsx"
    try:
        patents_data = state.get("patents_data", {})

        # Rebuild the COMPLETE tree from final_taxonomy (includes injected granular leaf nodes)
        def _rebuild_tree_from_taxonomy(taxonomy_nodes: list) -> dict:
            nodes_by_id = {n["node_id"]: n for n in taxonomy_nodes}
            roots = [n for n in taxonomy_nodes if n["parent_node_id"] is None]

            def _build(node_id):
                children = [n for n in taxonomy_nodes if n["parent_node_id"] == node_id]
                if not children:
                    return {}
                return {c["name"]: _build(c["node_id"]) for c in children}

            tree = {}
            for root in roots:
                tree[root["name"]] = _build(root["node_id"])
            return tree

        enriched_tree = _rebuild_tree_from_taxonomy(final_taxonomy)
        generate_dynamic_matrix_excel(patents_data, final_taxonomy, enriched_tree, matrix_path)
        print(f"-> Generated dynamic Matrix Excel at {matrix_path}")
    except Exception as e:
        import traceback
        print(f"Failed to generate Matrix Excel: {e}")
        traceback.print_exc()

    # 3. Write the HTML Interactive Graph to data/
    html_path = f"c:\\Users\\Vipul\\Desktop\\taxonomies_agent\\data\\taxonomy_graph_{run_id}.html"
    try:
        generate_html_graph(draft_tree, html_path)
        print(f"-> Generated interactive HTML graph at {html_path}")
    except Exception as e:
        print(f"Failed to generate HTML graph: {e}")
        
    out_data = {"run_id": run_id}
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(run_id, "format_taxonomy", state, out_data)
        
    return out_data
