"""
export_manager.py — Central Manager & Registry for Dynamic Document & Sheet Exports.

Orchestrates generation of PDFs and Excel spreadsheets, persists them
to disk with unique IDs, and provides lookup for download endpoints.
"""

import os
import uuid
import datetime
from typing import Dict, Any, List, Optional

from .excel_generator import build_dynamic_excel
from .pdf_generator import build_dynamic_pdf

# Exports directory: persists under web_app/backend/exports/
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web_app", "backend"))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

# In-memory registry for file metadata lookup (backed by filesystem)
_EXPORT_REGISTRY: Dict[str, Dict[str, Any]] = {}


def export_document(
    title: str,
    export_format: str,  # "excel", "xlsx", "sheet", "pdf"
    tables: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    summary: Optional[str] = None,
    sections: Optional[List[Dict[str, str]]] = None,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dynamically generates either an Excel sheet or a PDF report and registers it for download.

    Returns:
        Dict with:
            - "file_id": unique identifier for download
            - "file_name": safe display filename
            - "format": "excel" or "pdf"
            - "download_url": "/api/export/download/{file_id}"
            - "file_path": path on disk
            - "file_size_bytes": size in bytes
    """
    file_id = str(uuid.uuid4())
    norm_format = export_format.lower().strip()
    is_pdf = "pdf" in norm_format

    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    if not safe_title:
        safe_title = "Report"

    extension = "pdf" if is_pdf else "xlsx"
    file_name = f"{safe_title}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{extension}"
    file_path = os.path.join(EXPORTS_DIR, f"{file_id}_{file_name}")

    # Build the document
    if is_pdf:
        build_dynamic_pdf(
            file_path=file_path,
            title=title,
            tables=tables,
            metadata=metadata,
            summary=summary,
            sections=sections
        )
    else:
        build_dynamic_excel(
            file_path=file_path,
            title=title,
            tables=tables,
            metadata=metadata,
            summary=summary
        )

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    record = {
        "file_id": file_id,
        "file_name": file_name,
        "format": "pdf" if is_pdf else "excel",
        "file_path": file_path,
        "file_size_bytes": file_size,
        "run_id": run_id,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "download_url": f"/api/export/download/{file_id}"
    }

    _EXPORT_REGISTRY[file_id] = record
    return record


def get_export_file(file_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves file record by file_id, checking in-memory and filesystem."""
    # Check in-memory first
    if file_id in _EXPORT_REGISTRY:
        record = _EXPORT_REGISTRY[file_id]
        if os.path.exists(record["file_path"]):
            return record

    # Fallback: scan EXPORTS_DIR for file prefixed with file_id
    if os.path.exists(EXPORTS_DIR):
        for fname in os.listdir(EXPORTS_DIR):
            if fname.startswith(f"{file_id}_"):
                full_path = os.path.join(EXPORTS_DIR, fname)
                orig_name = fname[len(file_id) + 1:]
                fmt = "pdf" if fname.endswith(".pdf") else "excel"
                record = {
                    "file_id": file_id,
                    "file_name": orig_name,
                    "format": fmt,
                    "file_path": full_path,
                    "file_size_bytes": os.path.getsize(full_path),
                    "download_url": f"/api/export/download/{file_id}"
                }
                _EXPORT_REGISTRY[file_id] = record
                return record

    return None
