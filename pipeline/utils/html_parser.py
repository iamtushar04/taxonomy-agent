"""
HTML parser for patent structured_description.

The Wissen Patent API returns `structured_description` as raw HTML.
This module converts it into labelled text chunks that the extraction
pipeline can process:

  - Plain paragraphs        → section "description"
  - <table> elements        → section "table", rendered as markdown table
  - Example sections        → section "description", source_label "Example N"
  - Figure captions         → section "figure"

All chunks follow the PatentChunk TypedDict contract.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

from pipeline.state import PatentChunk

logger = logging.getLogger(__name__)

# Priority constants (lower number = higher extraction priority)
PRIORITY_CLAIM = 1
PRIORITY_EXAMPLE = 2
PRIORITY_TABLE = 2
PRIORITY_DESCRIPTION = 3
PRIORITY_FIGURE = 3
PRIORITY_ABSTRACT = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk_id(patent_number: str, section: str, index: int) -> str:
    raw = f"{patent_number}::{section}::{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:10]


def _clean_text(text: str) -> str:
    """Remove excessive whitespace from extracted text."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _table_to_markdown(table_tag: Tag) -> str:
    """Convert a BeautifulSoup <table> to a compact markdown table string, respecting colspan and rowspan."""
    rows = table_tag.find_all("tr")
    if not rows:
        return ""

    grid = {}
    max_col = 0
    
    for r_idx, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        c_idx = 0
        for cell in cells:
            while grid.get((r_idx, c_idx)) is not None:
                c_idx += 1
            
            try:
                colspan = int(cell.get("colspan", 1))
            except (ValueError, TypeError):
                colspan = 1
                
            try:
                rowspan = int(cell.get("rowspan", 1))
            except (ValueError, TypeError):
                rowspan = 1
                
            text = _clean_text(cell.get_text())
            
            for r in range(rowspan):
                for c in range(colspan):
                    # Repeat text to ensure every expanded column has the label explicitly
                    grid[(r_idx + r, c_idx + c)] = text 
            
            c_idx += colspan
            max_col = max(max_col, c_idx)

    if max_col == 0:
        return ""

    md_rows = []
    for r_idx in range(len(rows)):
        row_data = [grid.get((r_idx, c), "") for c in range(max_col)]
        md_rows.append("| " + " | ".join(row_data) + " |")
        if r_idx == 0:
            md_rows.append("|" + "|".join(["---"] * max_col) + "|")

    return "\n".join(md_rows)


def _detect_example_number(text: str) -> Optional[str]:
    """
    Detect if a paragraph starts an Example section.
    Returns 'Example N' or None.
    """
    match = re.match(r"^\s*example\s+(\d+|[IVXLC]+)\b", text, re.IGNORECASE)
    if match:
        return f"Example {match.group(1)}"
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_structured_description(
    html: str,
    patent_number: str,
) -> list[PatentChunk]:
    """
    Parse the raw HTML from `structured_description` into PatentChunks.

    Processing order:
      1. Extract and convert all <table> elements first.
      2. Walk remaining text by paragraph, detecting Example sections.
      3. Extract figure captions.

    Args:
        html:           Raw HTML string from the API.
        patent_number:  Used to build unique chunk IDs.

    Returns:
        List of PatentChunk dicts, ready to merge with claims/abstract chunks.
    """
    # structured_description can be a list of HTML strings or a single string
    if isinstance(html, list):
        html = "\n".join(str(item) for item in html if item)

    if not html or not html.strip():
        return []


    soup = BeautifulSoup(html, "lxml")
    chunks: list[PatentChunk] = []
    chunk_counter = 0

    # ── Step 1: Tables ──────────────────────────────────────────────────────
    for table_idx, table in enumerate(soup.find_all("table"), start=1):
        md = _table_to_markdown(table)
        if not md:
            table.decompose()
            continue

        # Try to find a nearby caption / label
        caption_tag = table.find("caption")
        caption = _clean_text(caption_tag.get_text()) if caption_tag else ""
        source_label = f"Table {table_idx}" + (f" ({caption})" if caption else "")

        chunks.append(PatentChunk(
            chunk_id=_chunk_id(patent_number, "table", chunk_counter),
            section="table",
            source_label=source_label,
            priority=PRIORITY_TABLE,
            text=f"[{source_label}]\n{md}",
        ))
        chunk_counter += 1
        table.decompose()   # remove so it doesn't appear in paragraph text

    # ── Step 2: Figures / images ────────────────────────────────────────────
    for fig_idx, fig in enumerate(
        soup.find_all(["figure", "figcaption"]), start=1
    ):
        caption = _clean_text(fig.get_text())
        if len(caption) < 5:
            continue
        chunks.append(PatentChunk(
            chunk_id=_chunk_id(patent_number, "figure", chunk_counter),
            section="figure",
            source_label=f"Figure {fig_idx}",
            priority=PRIORITY_FIGURE,
            text=f"[Figure {fig_idx} caption] {caption}",
        ))
        chunk_counter += 1
        fig.decompose()

    # ── Step 3: Paragraphs / example sections ──────────────────────────────
    current_example: Optional[str] = None

    # Walk top-level block elements
    block_tags = soup.find_all(
        ["p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6", "li"]
    )

    if not block_tags:
        # Fallback: just dump all remaining text
        text = _clean_text(soup.get_text())
        if text:
            chunks.append(PatentChunk(
                chunk_id=_chunk_id(patent_number, "description", chunk_counter),
                section="description",
                source_label="Description",
                priority=PRIORITY_DESCRIPTION,
                text=text,
            ))
        return chunks

    for tag in block_tags:
        text = _clean_text(tag.get_text())
        if not text or len(text) < 10:
            continue

        # Detect example markers
        example_label = _detect_example_number(text)
        if example_label:
            current_example = example_label

        section = "description"
        source_label = current_example if current_example else "Description"
        priority = PRIORITY_EXAMPLE if current_example else PRIORITY_DESCRIPTION

        chunks.append(PatentChunk(
            chunk_id=_chunk_id(patent_number, section, chunk_counter),
            section=section,
            source_label=source_label,
            priority=priority,
            text=text,
        ))
        chunk_counter += 1

    logger.debug(
        "Parsed structured_description: %d chunks (%d tables, %d figures, %d paragraphs)",
        len(chunks),
        sum(1 for c in chunks if c["section"] == "table"),
        sum(1 for c in chunks if c["section"] == "figure"),
        sum(1 for c in chunks if c["section"] == "description"),
    )
    return chunks


def parse_claims_text(
    claims_text: str,
    structured_claims: list[dict],
    patent_number: str,
) -> list[PatentChunk]:
    """
    Convert the claims field(s) from the API into PatentChunks.

    Prefers structured_claims (element-level) when available;
    falls back to splitting the flat claims string by claim number.

    Independent claims get priority=1, dependent claims get priority=2.
    """
    chunks: list[PatentChunk] = []

    if structured_claims:
        for claim in structured_claims:
            num = claim.get("claim_number", "?").lstrip("0") or "?"
            is_independent = claim.get("is_independent", False)
            text = _clean_text(claim.get("claim_text", ""))
            if not text:
                continue
            chunks.append(PatentChunk(
                chunk_id=_chunk_id(patent_number, "claim", int(num) if num.isdigit() else 0),
                section="claims",
                source_label=f"Claim {num}",
                priority=PRIORITY_CLAIM if is_independent else 2,
                text=text,
            ))
        return chunks

    # Fallback: split flat string on "N. " pattern
    if not claims_text:
        return chunks

    parts = re.split(r"(?=\b\d+\.\s)", claims_text)
    for part in parts:
        part = _clean_text(part)
        if not part:
            continue
        m = re.match(r"^(\d+)\.", part)
        num = m.group(1) if m else "?"
        chunks.append(PatentChunk(
            chunk_id=_chunk_id(patent_number, "claim", int(num) if num.isdigit() else 0),
            section="claims",
            source_label=f"Claim {num}",
            priority=PRIORITY_CLAIM,
            text=part,
        ))

    return chunks
