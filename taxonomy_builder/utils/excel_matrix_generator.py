import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from typing import List, Dict, Any

def get_max_depth(tree_dict, current=0):
    if not tree_dict:
        return current
    return max(get_max_depth(v, current + 1) for v in tree_dict.values() if isinstance(v, dict))

def write_tree_headers_to_sheet(ws, tree_dict, max_depth, start_col=6, palette=None):
    if palette is None:
        palette = ["92D050", "00B0F0", "FFC000", "B1A0C7", "FFFF00", "B7DEE8", "D9E1F2", "FCE4D6"]
    dynamic_header_font = Font(bold=True, color="000000")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    leaf_col_map = {}

    def _recurse(subtree, row, col_offset, color_idx=0):
        if not subtree:
            return 1
        total_span = 0
        for i, (node_name, children) in enumerate(subtree.items()):
            cur_color_idx = (color_idx + i) % len(palette) if row == 1 else color_idx
            fill_color = palette[cur_color_idx]
            child_span = _recurse(children, row + 1, col_offset + total_span, cur_color_idx)

            cell = ws.cell(row=row, column=col_offset + total_span, value=node_name)
            cell.font = dynamic_header_font
            cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
            cell.alignment = center_align

            if child_span > 1:
                ws.merge_cells(
                    start_row=row,
                    start_column=col_offset + total_span,
                    end_row=row,
                    end_column=col_offset + total_span + child_span - 1
                )
            else:
                if not children:
                    leaf_col_map[node_name] = col_offset + total_span
                    if row < max_depth:
                        ws.merge_cells(
                            start_row=row,
                            start_column=col_offset + total_span,
                            end_row=max_depth,
                            end_column=col_offset + total_span
                        )
            total_span += child_span
        return total_span

    _recurse(tree_dict, row=1, col_offset=start_col)

    # Set width for dynamic leaf columns
    for leaf_name, c_idx in leaf_col_map.items():
        col_letter = openpyxl.utils.get_column_letter(c_idx)
        ws.column_dimensions[col_letter].width = 35

    return leaf_col_map


def generate_dynamic_matrix_excel(
    patents_data: dict, 
    final_taxonomy: List[Dict], 
    draft_tree: dict, 
    output_path: str, 
    input_ids: List[str] = None,
    products_data: Any = None
):
    """
    Generates a dynamically structured multi-sheet Excel file matching exact corporate specifications:
    - Sheet 1: 'Patent Taxonomy Matrix' (Rows = Patents, Columns = Hierarchical taxonomy tree)
    - Sheet 2: 'Product Taxonomy Matrix' (Rows = Products, Columns = Exact same hierarchical taxonomy tree)
    - Sheet 3: 'Commercial Products Specifications' (Comprehensive technical features & specifications catalogue)
    """
    wb = openpyxl.Workbook()
    
    fixed_header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid") # Dark Blue
    fixed_header_font = Font(bold=True, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_align = Alignment(horizontal="left", vertical="top", wrap_text=True)
    palette = ["92D050", "00B0F0", "FFC000", "B1A0C7", "FFFF00", "B7DEE8", "D9E1F2", "FCE4D6"]

    max_depth = get_max_depth(draft_tree)
    if max_depth == 0:
        max_depth = 1

    # Extract products data if embedded in patents_data or passed separately
    if products_data is None and isinstance(patents_data, dict):
        products_data = patents_data.get("_products")

    products_list = []
    if isinstance(products_data, dict):
        for pid, pval in products_data.items():
            if isinstance(pval, dict):
                p_copy = dict(pval)
                if "product_id" not in p_copy:
                    p_copy["product_id"] = pid
                products_list.append(p_copy)
    elif isinstance(products_data, list):
        for idx, pval in enumerate(products_data):
            if isinstance(pval, dict):
                p_copy = dict(pval)
                if "product_id" not in p_copy:
                    p_copy["product_id"] = f"prod_{idx+1}"
                products_list.append(p_copy)

    # Determine patent rows to generate
    order = input_ids if input_ids else [k for k in patents_data.keys() if k != "_products"]
    patent_keys = [pid for pid in order if pid != "_products" and pid in patents_data]

    has_patents = len(patent_keys) > 0
    has_products = len(products_list) > 0

    # ─────────────────────────────────────────────────────────────
    # SHEET 1: PATENT TAXONOMY MATRIX
    # ─────────────────────────────────────────────────────────────
    if has_patents or not has_products:
        ws_pat = wb.active
        ws_pat.title = "Patent Taxonomy Matrix"

        fixed_headers = ["S.No", "Patent Number", "Patent Title", "Assignee", "Summary"]
        for col_idx, header in enumerate(fixed_headers, start=1):
            cell = ws_pat.cell(row=1, column=col_idx, value=header)
            cell.font = fixed_header_font
            cell.fill = fixed_header_fill
            cell.alignment = center_align
            if max_depth > 1:
                ws_pat.merge_cells(start_row=1, start_column=col_idx, end_row=max_depth, end_column=col_idx)

        col_widths = {1: 10, 2: 20, 3: 45, 4: 40, 5: 60}
        for col_idx, width in col_widths.items():
            ws_pat.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

        leaf_col_map_pat = write_tree_headers_to_sheet(
            ws_pat, draft_tree, max_depth, start_col=len(fixed_headers) + 1, palette=palette
        )

        row_idx = max_depth + 1
        for patent_id in patent_keys:
            p_data = patents_data.get(patent_id, {})
            ws_pat.cell(row=row_idx, column=1, value=row_idx - max_depth).alignment = cell_align
            ws_pat.cell(row=row_idx, column=2, value=patent_id).alignment = cell_align
            ws_pat.cell(row=row_idx, column=3, value=p_data.get("title", "N/A")).alignment = cell_align
            ws_pat.cell(row=row_idx, column=4, value=p_data.get("assignee", "N/A")).alignment = cell_align

            summary_text = p_data.get("summary", "N/A")
            if len(summary_text) > 200:
                summary_text = summary_text[:200] + "..."
            ws_pat.cell(row=row_idx, column=5, value=summary_text).alignment = cell_align

            for leaf_name, col_idx in leaf_col_map_pat.items():
                node = next((n for n in final_taxonomy if n.get("name") == leaf_name), None)
                if node and patent_id in node.get("supporting_patent_ids", []):
                    patent_specific_contexts = node.get("contexts_by_patent", {}).get(patent_id, [])
                    if patent_specific_contexts:
                        contexts = "\n\n".join(patent_specific_contexts)
                        ws_pat.cell(row=row_idx, column=col_idx, value=contexts).alignment = cell_align
                    else:
                        ws_pat.cell(row=row_idx, column=col_idx, value="✓").alignment = center_align
                else:
                    ws_pat.cell(row=row_idx, column=col_idx, value="-").alignment = center_align

            row_idx += 1

    # ─────────────────────────────────────────────────────────────
    # SHEET 2: PRODUCT TAXONOMY MATRIX (SAME STRUCTURE & DESIGN)
    # ─────────────────────────────────────────────────────────────
    if has_products:
        if has_patents:
            ws_prod = wb.create_sheet(title="Product Taxonomy Matrix")
        else:
            ws_prod = wb.active
            ws_prod.title = "Product Taxonomy Matrix"

        prod_fixed_headers = ["S.No", "Product Name", "Assignee / Company", "Category / Domain", "Source Link / Document"]
        for col_idx, header in enumerate(prod_fixed_headers, start=1):
            cell = ws_prod.cell(row=1, column=col_idx, value=header)
            cell.font = fixed_header_font
            cell.fill = fixed_header_fill
            cell.alignment = center_align
            if max_depth > 1:
                ws_prod.merge_cells(start_row=1, start_column=col_idx, end_row=max_depth, end_column=col_idx)

        prod_col_widths = {1: 10, 2: 30, 3: 30, 4: 28, 5: 45}
        for col_idx, width in prod_col_widths.items():
            ws_prod.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

        leaf_col_map_prod = write_tree_headers_to_sheet(
            ws_prod, draft_tree, max_depth, start_col=len(prod_fixed_headers) + 1, palette=palette
        )

        prod_row_idx = max_depth + 1
        for p_info in products_list:
            prod_id = p_info.get("product_id", "")
            prod_name = p_info.get("product_name") or prod_id or "Unknown Product"
            brand = p_info.get("brand_or_assignee") or "Unknown"
            cat = p_info.get("category") or "Uncategorized"
            source_file = p_info.get("source_filename") or p_info.get("url") or "Uploaded Document"

            ws_prod.cell(row=prod_row_idx, column=1, value=prod_row_idx - max_depth).alignment = cell_align
            ws_prod.cell(row=prod_row_idx, column=2, value=prod_name).alignment = cell_align
            ws_prod.cell(row=prod_row_idx, column=3, value=brand).alignment = cell_align
            ws_prod.cell(row=prod_row_idx, column=4, value=cat).alignment = cell_align
            ws_prod.cell(row=prod_row_idx, column=5, value=source_file).alignment = cell_align

            p_features = p_info.get("features", [])
            p_snippet = p_info.get("full_text_snippet", "")

            for leaf_name, col_idx in leaf_col_map_prod.items():
                node = next((n for n in final_taxonomy if n.get("name") == leaf_name), None)
                is_mapped = False
                evidence = ""

                if node:
                    sup_pids = node.get("supporting_product_ids") or []
                    if (prod_id and prod_id in sup_pids) or (prod_name and prod_name in sup_pids):
                        is_mapped = True

                    # Check explicit contexts
                    p_contexts = node.get("contexts_by_product", {}).get(prod_id) or node.get("contexts_by_product", {}).get(prod_name)
                    if p_contexts:
                        is_mapped = True
                        evidence = "\n\n".join(p_contexts) if isinstance(p_contexts, list) else str(p_contexts)

                    # Substring match against product features as fallback evidence
                    if not is_mapped and p_features:
                        ln_lower = leaf_name.lower()
                        matching_feats = [f for f in p_features if ln_lower in f.lower() or any(w in f.lower() for w in ln_lower.split() if len(w) > 3)]
                        if matching_feats:
                            is_mapped = True
                            evidence = "\n".join(f"• {mf}" for mf in matching_feats[:3])

                if is_mapped:
                    val = evidence if evidence else "✓"
                    ws_prod.cell(row=prod_row_idx, column=col_idx, value=val).alignment = cell_align if evidence else center_align
                else:
                    ws_prod.cell(row=prod_row_idx, column=col_idx, value="-").alignment = center_align

            prod_row_idx += 1

        # ─────────────────────────────────────────────────────────────
        # SHEET 3: COMMERCIAL PRODUCTS SPECIFICATIONS
        # ─────────────────────────────────────────────────────────────
        ws_specs = wb.create_sheet(title="Product Specifications")
        spec_headers = [
            "S.No", 
            "Product Name", 
            "Assignee / Company", 
            "Category / Domain", 
            "Source Link / Document", 
            "Key Technical Features & Claims", 
            "Specifications & Property Details"
        ]
        for col_idx, header in enumerate(spec_headers, start=1):
            cell = ws_specs.cell(row=1, column=col_idx, value=header)
            cell.font = fixed_header_font
            cell.fill = fixed_header_fill
            cell.alignment = center_align

        spec_col_widths = {1: 10, 2: 30, 3: 25, 4: 25, 5: 42, 6: 45, 7: 65}
        for col_idx, width in spec_col_widths.items():
            ws_specs.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

        spec_row_idx = 2
        for idx, p_info in enumerate(products_list, start=1):
            prod_name = p_info.get("product_name") or p_info.get("product_id") or "Unknown Product"
            brand = p_info.get("brand_or_assignee") or "Unknown"
            cat = p_info.get("category") or "Uncategorized"
            source_file = p_info.get("source_filename") or p_info.get("url") or "Uploaded Document"

            features_list = p_info.get("features", [])
            formatted_features = "\n".join(f"• {f}" for f in features_list) if features_list else "N/A"

            snippet = p_info.get("full_text_snippet", "")
            if len(snippet) > 2500:
                snippet = snippet[:2500] + "..."
            if not snippet:
                snippet = "N/A"

            ws_specs.cell(row=spec_row_idx, column=1, value=idx).alignment = cell_align
            ws_specs.cell(row=spec_row_idx, column=2, value=prod_name).alignment = cell_align
            ws_specs.cell(row=spec_row_idx, column=3, value=brand).alignment = cell_align
            ws_specs.cell(row=spec_row_idx, column=4, value=cat).alignment = cell_align
            ws_specs.cell(row=spec_row_idx, column=5, value=source_file).alignment = cell_align
            ws_specs.cell(row=spec_row_idx, column=6, value=formatted_features).alignment = cell_align
            ws_specs.cell(row=spec_row_idx, column=7, value=snippet).alignment = cell_align

            spec_row_idx += 1

    wb.save(output_path)
