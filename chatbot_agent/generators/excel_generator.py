"""
excel_generator.py — Dynamic, Modular Excel Spreadsheet Builder.

Builds structured, beautifully formatted .xlsx workbooks from arbitrary
dynamic table definitions supplied by the AI agent or application.
"""

import os
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any, Optional

# Color Palette for Headers & Highlights
NAVY_HEADER = "1E293B"
EMERALD_ACCENT = "059669"
LIGHT_GRAY_FILL = "F8FAFC"
ALT_ROW_FILL = "F1F5F9"
BORDER_COLOR = "CBD5E1"


def build_dynamic_excel(
    file_path: str,
    title: str,
    tables: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    summary: Optional[str] = None
) -> str:
    """
    Creates an Excel spreadsheet dynamically with one or more sheets.

    Args:
        file_path: Destination path on disk.
        title: Overall title of the workbook / primary sheet.
        tables: List of sheet dictionaries. Each must contain:
            - "sheet_title": str
            - "columns": List[str]
            - "rows": List[List[Any]]
            - "column_widths": Optional[Dict[int, int]] (1-indexed)
        metadata: Optional dictionary of key-value pairs to display at the top.
        summary: Optional narrative summary / key findings paragraph.
    
    Returns:
        file_path where file was saved.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    wb = openpyxl.Workbook()

    thin_border = Border(
        left=Side(style='thin', color=BORDER_COLOR),
        right=Side(style='thin', color=BORDER_COLOR),
        top=Side(style='thin', color=BORDER_COLOR),
        bottom=Side(style='thin', color=BORDER_COLOR)
    )

    for sheet_idx, table in enumerate(tables):
        sheet_title = table.get("sheet_title") or f"Sheet {sheet_idx + 1}"
        # Excel sheet titles max 31 chars and no invalid chars
        safe_title = "".join(c for c in sheet_title if c not in r"[]:*?/\\")[:30]

        if sheet_idx == 0:
            ws = wb.active
            ws.title = safe_title
        else:
            ws = wb.create_sheet(title=safe_title)

        ws.views.sheetView[0].showGridLines = True
        current_row = 1

        # 1. Main Title Banner (Only on Sheet 1 or if explicit)
        if sheet_idx == 0:
            title_cell = ws.cell(row=current_row, column=1, value=f"📊 {title}")
            title_cell.font = Font(name="Calibri", size=16, bold=True, color="0F172A")
            ws.row_dimensions[current_row].height = 28
            current_row += 1

            # Summary block
            if summary:
                sum_cell = ws.cell(row=current_row, column=1, value=summary)
                sum_cell.font = Font(name="Calibri", size=11, italic=True, color="475569")
                sum_cell.alignment = Alignment(wrap_text=True)
                current_row += 2

            # Metadata block
            if metadata:
                for k, v in metadata.items():
                    k_cell = ws.cell(row=current_row, column=1, value=f"{k}:")
                    k_cell.font = Font(name="Calibri", size=10, bold=True, color="64748B")
                    v_cell = ws.cell(row=current_row, column=2, value=str(v))
                    v_cell.font = Font(name="Calibri", size=10, color="0F172A")
                    current_row += 1
                current_row += 1

        # 2. Table Column Headers
        columns = table.get("columns", [])
        rows = table.get("rows", [])

        if columns:
            header_fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

            ws.row_dimensions[current_row].height = 26
            for col_idx, col_name in enumerate(columns, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=str(col_name))
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
                cell.border = thin_border

            current_row += 1

            # 3. Table Rows
            data_align_left = Alignment(horizontal="left", vertical="top", wrap_text=True)
            data_align_center = Alignment(horizontal="center", vertical="top", wrap_text=True)
            data_font = Font(name="Calibri", size=10, color="0F172A")
            alt_fill = PatternFill(start_color=ALT_ROW_FILL, end_color=ALT_ROW_FILL, fill_type="solid")

            for r_idx, row_data in enumerate(rows):
                ws.row_dimensions[current_row].height = 20
                is_alt = (r_idx % 2 == 1)

                for c_idx, val in enumerate(row_data, start=1):
                    # Format strings, lists, or booleans
                    if isinstance(val, list):
                        display_val = "\n".join(f"• {item}" for item in val)
                    elif isinstance(val, bool):
                        display_val = "Yes" if val else "No"
                    elif val is None:
                        display_val = "—"
                    else:
                        display_val = str(val)

                    cell = ws.cell(row=current_row, column=c_idx, value=display_val)
                    cell.font = data_font
                    cell.border = thin_border
                    if is_alt:
                        cell.fill = alt_fill

                    # Align dates and numbers to center, long text to left
                    if len(display_val) <= 12 and ("-" in display_val or display_val.isdigit() or display_val in ["Yes", "No", "—"]):
                        cell.alignment = data_align_center
                    else:
                        cell.alignment = data_align_left

                current_row += 1

            # 4. Auto-fit Column Widths (or apply custom)
            custom_widths = table.get("column_widths", {})
            for col_idx in range(1, len(columns) + 1):
                col_letter = get_column_letter(col_idx)
                if col_idx in custom_widths:
                    ws.column_dimensions[col_letter].width = custom_widths[col_idx]
                else:
                    # Calculate max length
                    max_len = len(str(columns[col_idx - 1]))
                    for row_data in rows[:100]:  # sample first 100 rows
                        if col_idx - 1 < len(row_data):
                            val_str = str(row_data[col_idx - 1] or "")
                            first_line = val_str.split("\n")[0]
                            max_len = max(max_len, min(len(first_line), 55))
                    ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    wb.save(file_path)
    return file_path
