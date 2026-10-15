"""
pdf_generator.py — Dynamic, Modular Corporate PDF Report Builder.

Builds structured, professionally styled PDF reports from arbitrary
dynamic table definitions and executive summaries supplied by the AI agent.
"""

import os
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds 'Page X of Y' and confidential header to each page."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(self._pagesize[0] - 36, 24, page_text)
        self.drawString(36, 24, "Taxonomy Intelligence Co-Pilot • Commercial & IP Coverage Analysis")

        # Subtle footer separator line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 34, self._pagesize[0] - 36, 34)

        self.restoreState()


def build_dynamic_pdf(
    file_path: str,
    title: str,
    tables: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    summary: Optional[str] = None,
    sections: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Creates a publication-quality PDF report dynamically.

    Args:
        file_path: Output file path.
        title: Document title.
        tables: List of table dictionaries:
            - "sheet_title": str (heading for table)
            - "columns": List[str]
            - "rows": List[List[Any]]
        metadata: Key-value metadata (e.g. Workspace, Generated Date).
        summary: Executive summary paragraph.
        sections: Optional extra narrative sections [{"heading": "...", "content": "..."}].

    Returns:
        file_path where file was saved.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Determine orientation: If max columns across tables > 5, use Landscape
    max_cols = max((len(t.get("columns", [])) for t in tables), default=4)
    page_size = landscape(A4) if max_cols >= 5 else A4
    page_width, page_height = page_size

    margin = 36  # 0.5 inch margins
    printable_width = page_width - (2 * margin)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=40,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )

    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=14,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#0F172A')
    )

    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=1  # Centered
    )

    td_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#1E293B')
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph(f"<b>{title}</b>", title_style))
    story.append(Paragraph("Generated by Autonomous Taxonomy Intelligence Agent", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=0, spaceAfter=10))

    # 2. Metadata & Summary Card
    if summary or metadata:
        meta_elements = []
        if metadata:
            meta_strings = [f"<b>{k}:</b> {v}" for k, v in metadata.items()]
            meta_elements.append(Paragraph(" • ".join(meta_strings), subtitle_style))
        if summary:
            meta_elements.append(Spacer(1, 4))
            meta_elements.append(Paragraph(f"<b>Executive Summary:</b> {summary}", callout_style))

        # Box card
        summary_table = Table([[meta_elements]], colWidths=[printable_width])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 12))

    # 3. Extra Narrative Sections (if provided)
    if sections:
        for sec in sections:
            story.append(Paragraph(sec.get("heading", "Analysis"), h2_style))
            story.append(Paragraph(sec.get("content", ""), body_style))
            story.append(Spacer(1, 6))

    # 4. Tables
    for t_idx, table_dict in enumerate(tables):
        sheet_title = table_dict.get("sheet_title")
        if sheet_title:
            story.append(Paragraph(f"📊 {sheet_title}", h2_style))

        columns = table_dict.get("columns", [])
        rows = table_dict.get("rows", [])

        if not columns or not rows:
            story.append(Paragraph("<i>No data rows available.</i>", body_style))
            continue

        num_cols = len(columns)
        # Calculate dynamic column width: distribute printable width fairly
        col_width = printable_width / num_cols
        col_widths = [col_width] * num_cols

        # Wrap text in Paragraphs to prevent overflow
        table_data = []

        # Header Row
        header_row = [Paragraph(f"<b>{str(col)}</b>", th_style) for col in columns]
        table_data.append(header_row)

        # Data Rows
        for r in rows:
            row_cells = []
            for item in r:
                if isinstance(item, list):
                    item_str = "<br/>• ".join(str(x) for x in item)
                    if item_str:
                        item_str = "• " + item_str
                elif item is None:
                    item_str = "—"
                else:
                    item_str = str(item).replace("\n", "<br/>")

                row_cells.append(Paragraph(item_str, td_style))
            # Pad if row has fewer cells than columns
            while len(row_cells) < num_cols:
                row_cells.append(Paragraph("—", td_style))
            table_data.append(row_cells[:num_cols])

        report_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        report_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))

        story.append(report_table)
        story.append(Spacer(1, 14))

    # Build PDF with page numbering canvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return file_path
