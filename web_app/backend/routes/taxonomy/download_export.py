"""
download_export.py — Download Endpoint for Dynamically Generated Agent Documents (PDF & Excel).

Streams files created by the chatbot agent directly to the user's browser.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import urllib.parse

from chatbot_agent.generators.export_manager import get_export_file, export_document

router = APIRouter()


@router.post("/api/export/generate")
async def generate_dynamic_export(payload: dict):
    """
    Generates a dynamic PDF or Excel export on demand and returns the file download metadata.
    """
    try:
        title = payload.get("title", "Export Report")
        export_format = payload.get("format", "excel")
        tables = payload.get("tables", [])
        summary = payload.get("summary")
        metadata = payload.get("metadata")
        sections = payload.get("sections")
        run_id = payload.get("run_id")

        record = export_document(
            title=title,
            export_format=export_format,
            tables=tables,
            metadata=metadata,
            summary=summary,
            sections=sections,
            run_id=run_id
        )
        return {
            "status": "success",
            "file_id": record["file_id"],
            "file_name": record["file_name"],
            "format": record["format"],
            "download_url": record["download_url"],
            "file_size_bytes": record["file_size_bytes"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate export: {str(e)}")


@router.get("/api/export/download/{file_id}")
async def download_dynamic_export(file_id: str):
    """
    Downloads a dynamically generated PDF or Excel file created by the agent.
    Publicly accessible via unique UUID token to allow instant browser downloads.
    """
    file_record = get_export_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="Requested export document not found or expired.")

    file_path = file_record.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file missing from server storage.")

    file_name = file_record.get("file_name", f"Export_{file_id}.xlsx")
    is_pdf = file_name.lower().endswith(".pdf") or file_record.get("format") == "pdf"

    media_type = "application/pdf" if is_pdf else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    encoded_filename = urllib.parse.quote(file_name)

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=media_type,
        headers={
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Content-Disposition": f'attachment; filename="{file_name}"; filename*=UTF-8\'\'{encoded_filename}'
        }
    )

