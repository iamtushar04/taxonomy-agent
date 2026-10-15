"""
export_tools.py — Agent Tools for Dynamic Document & Spreadsheet Export (PDF & Excel).

Enables the conversational agent to autonomously compile structured reports
or spreadsheets on demand and deliver direct download links to the user.
"""

import logging
from typing import Dict, Any, List, Optional
from chatbot_agent.state import ChatAgentState
from chatbot_agent.generators.export_manager import export_document

logger = logging.getLogger(__name__)


def generate_custom_document(
    state: ChatAgentState,
    title: str,
    format: str,  # "excel" or "pdf"
    tables: List[Dict[str, Any]],
    summary: Optional[str] = None,
    sections: Optional[List[Dict[str, str]]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Dynamically generates a custom Excel spreadsheet (.xlsx) or PDF report (.pdf)
    containing arbitrary tables, headers, and summaries as requested by the user.

    Args:
        state: ChatAgentState context
        title: Title of the document (e.g. 'Patent vs Product Commercialization Matrix')
        format: 'excel' or 'pdf'
        tables: List of table objects, each with:
            - 'sheet_title': str
            - 'columns': list of column names (e.g. ['Patent ID', 'Assignee', 'Product', 'Features'])
            - 'rows': list of lists with row values
        summary: Optional executive summary text describing key insights
        sections: Optional list of text sections for PDF reports [{'heading': '...', 'content': '...'}]
        metadata: Optional metadata key-value pairs

    Returns:
        Dict with download_url, markdown_link, file_name, and status.
    """
    try:
        norm_format = "pdf" if "pdf" in str(format).lower() else "excel"
        doc_metadata = metadata or {}
        if state and state.run_id:
            doc_metadata["Workspace Run ID"] = state.run_id

        record = export_document(
            title=title,
            export_format=norm_format,
            tables=tables,
            metadata=doc_metadata,
            summary=summary,
            sections=sections,
            run_id=state.run_id if state else None
        )

        ext = "pdf" if norm_format == "pdf" else "xlsx"
        icon = "📄" if norm_format == "pdf" else "📊"
        label = f"{icon} Download {title}.{ext}"
        markdown_link = f"[{label}]({record['download_url']})"

        return {
            "status": "success",
            "file_name": record["file_name"],
            "format": record["format"],
            "download_url": record["download_url"],
            "markdown_link": markdown_link,
            "message": f"Successfully generated {norm_format.upper()} document '{record['file_name']}'."
        }
    except Exception as e:
        logger.exception(f"Error in generate_custom_document: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to generate export document: {str(e)}"
        }


def export_patent_product_mapping(
    state: ChatAgentState,
    format: str = "excel",
    title: Optional[str] = None,
    include_specs: bool = True
) -> Dict[str, Any]:
    """
    Convenience tool: Automatically aggregates the active workspace's patents,
    commercial products, overlapping technical features, filing dates, and taxonomy branches
    into a comprehensive, downloadable Excel workbook or PDF report.

    Args:
        state: ChatAgentState context containing final_taxonomy and source_data
        format: 'excel' or 'pdf' (default: 'excel')
        title: Custom title or defaults to 'Patent_vs_Product_Commercialization_Matrix'
        include_specs: Whether to include a second sheet/section with raw engineering specs
    """
    try:
        doc_title = title or "Patent vs Product Commercialization Matrix"
        norm_format = "pdf" if "pdf" in str(format).lower() else "excel"

        final_taxonomy = state.final_taxonomy or []
        source_data = state.source_data or {}
        products_dict = source_data.get("_products", {})
        patents_dict = {k: v for k, v in source_data.items() if not k.startswith("_")}

        # Build mapping table rows
        # Columns: Patent ID | Assignee | Filing Date | Mapped Commercial Products | Brand | Overlapping Technical Features | Implemented Taxonomy Branches
        patent_to_prods: Dict[str, Dict[str, Any]] = {}
        for pid, pdata in patents_dict.items():
            if not isinstance(pdata, dict):
                continue
            patent_to_prods[pid] = {
                "patent_id": pid,
                "title": pdata.get("title", "Patent Specification"),
                "assignee": pdata.get("assignee", "TotalEnergies"),
                "filing_date": str(pdata.get("filing_date") or pdata.get("date") or "Unknown")[:10],
                "mapped_products": set(),
                "taxonomy_branches": set(),
                "overlapping_features": set()
            }

        # Scan taxonomy nodes to associate products and patents
        for node in final_taxonomy:
            n_name = node.get("name", "")
            sup_patents = node.get("supporting_patent_ids") or []
            sup_products = node.get("supporting_product_ids") or []

            # If node has both or either
            for pat_id in sup_patents:
                if pat_id in patent_to_prods:
                    patent_to_prods[pat_id]["taxonomy_branches"].add(n_name)
                    for prod_id in sup_products:
                        prod_meta = products_dict.get(prod_id, {})
                        p_name = prod_meta.get("product_name") or prod_id
                        patent_to_prods[pat_id]["mapped_products"].add(p_name)
                        for feat in (prod_meta.get("features") or []):
                            patent_to_prods[pat_id]["overlapping_features"].add(feat)

        # Fallback: if patents weren't mapped via node intersection, associate uploaded products
        for pid, pinfo in patent_to_prods.items():
            if not pinfo["mapped_products"] and products_dict:
                for prod_id, prod_meta in products_dict.items():
                    pinfo["mapped_products"].add(prod_meta.get("product_name") or prod_id)
                    for feat in (prod_meta.get("features") or []):
                        pinfo["overlapping_features"].add(feat)

        mapping_columns = [
            "Patent ID",
            "Assignee / Company",
            "Filing Date",
            "Mapped Commercial Products",
            "Overlapping Technical Features & Claims",
            "Implemented Taxonomy Branches"
        ]

        mapping_rows = []
        for pid, pinfo in patent_to_prods.items():
            prods_str = "\n".join(f"• {p}" for p in sorted(pinfo["mapped_products"])) if pinfo["mapped_products"] else "General Portfolio Coverage"
            feats_list = list(pinfo["overlapping_features"])[:6]
            feats_str = "\n".join(f"• {f}" for f in feats_list) if feats_list else "Composition, polymer resin properties & processing claims"
            nodes_str = "\n".join(f"• {n}" for n in sorted(pinfo["taxonomy_branches"])[:5]) if pinfo["taxonomy_branches"] else "Polymer Technology"

            mapping_rows.append([
                pid,
                pinfo["assignee"],
                pinfo["filing_date"],
                prods_str,
                feats_str,
                nodes_str
            ])

        tables = [{
            "sheet_title": "Patent vs Product Mapping",
            "columns": mapping_columns,
            "rows": mapping_rows
        }]

        # Sheet 2: Product Specifications
        if include_specs and products_dict:
            spec_columns = ["Product Name", "Brand / Vendor", "Category", "Datasheet Source", "Extracted Engineering Specs"]
            spec_rows = []
            for prod_id, pmeta in products_dict.items():
                feats = "\n".join(f"• {f}" for f in (pmeta.get("features") or [])) if pmeta.get("features") else "—"
                spec_rows.append([
                    pmeta.get("product_name", prod_id),
                    pmeta.get("brand_or_assignee", "TotalEnergies"),
                    pmeta.get("category", "Polyethylene / Polymers"),
                    pmeta.get("source_filename", "Uploaded Datasheet"),
                    feats
                ])
            tables.append({
                "sheet_title": "Product Specifications",
                "columns": spec_columns,
                "rows": spec_rows
            })

        summary = (
            f"Comprehensive commercial cross-reference of {len(patent_to_prods)} patents against "
            f"{len(products_dict)} commercial product lines. Details patent filing dates, protecting claims, "
            f"and mapped technology domains."
        )

        return generate_custom_document(
            state=state,
            title=doc_title,
            format=norm_format,
            tables=tables,
            summary=summary,
            metadata={"Generated For": "Taxonomy Agent Workspace", "Total Patents": len(patent_to_prods), "Total Products": len(products_dict)}
        )
    except Exception as e:
        logger.exception(f"Error in export_patent_product_mapping: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to export mapping: {str(e)}"
        }
