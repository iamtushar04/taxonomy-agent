import os
import uuid
import re
import json
import io
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
# pyrefly: ignore [missing-import]
import pypdf
# pyrefly: ignore [missing-import]
import pdfplumber
# pyrefly: ignore [missing-import]
import docx
import httpx
from bs4 import BeautifulSoup

# pyrefly: ignore [missing-import]
from product_schemas import ParsedProduct


class URLFetcher:
    """
    Modular utility to fetch remote documents (PDFs, HTML specs) from web URLs.
    Handles redirects, user-agent headers, and mime-type detection.
    """

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8"
    }

    @classmethod
    def fetch_url(cls, url: str, timeout: float = 35.0) -> Tuple[Optional[bytes], str, str, Optional[str]]:
        """
        Fetches the content from a URL or local file path.
        Returns: (content_bytes, derived_filename, content_type, error_message)
        """
        raw_url = url.strip()

        # Check for local file path or file:// URL
        local_path = None
        if raw_url.lower().startswith("file:///"):
            local_path = urllib.parse.unquote(raw_url[8:])
            if len(local_path) > 2 and local_path[1] == ":" or (len(local_path) > 3 and local_path[0] == "/" and local_path[2] == ":"):
                local_path = local_path.lstrip("/")
        elif os.path.exists(raw_url) or (len(raw_url) > 2 and raw_url[1] == ":" and ("\\" in raw_url or "/" in raw_url)):
            local_path = raw_url

        if local_path and os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    content = f.read()
                filename = os.path.basename(local_path)
                content_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
                return content, filename, content_type, None
            except Exception as fe:
                return None, "", "", f"Failed to read local file {local_path}: {fe}"

        clean_url = raw_url
        if not clean_url.startswith(("http://", "https://")):
            clean_url = f"https://{clean_url}"

        try:
            with httpx.Client(follow_redirects=True, timeout=timeout, headers=cls.DEFAULT_HEADERS) as client:
                resp = client.get(clean_url)
                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "").lower()
                content = resp.content

                # Determine filename
                filename = cls._determine_filename(clean_url, resp.headers, content_type, content)
                return content, filename, content_type, None

        except httpx.HTTPStatusError as e:
            return None, "", "", f"HTTP error {e.response.status_code} while fetching {url}: {e.response.text[:200]}"
        except Exception as e:
            return None, "", "", f"Failed to fetch {url}: {str(e)}"

    @classmethod
    def _determine_filename(cls, url: str, headers: Dict[str, str], content_type: str, content: bytes) -> str:
        # Check Content-Disposition header
        cd = headers.get("content-disposition", "")
        if "filename=" in cd:
            match = re.search(r'filename=["\']?([^"\';]+)["\']?', cd)
            if match:
                return match.group(1).strip()

        # Check URL path
        parsed = urllib.parse.urlparse(url)
        path_name = os.path.basename(parsed.path)
        if path_name and ("." in path_name):
            return path_name

        # Detect from content magic bytes or Content-Type
        if content.startswith(b"%PDF") or "application/pdf" in content_type:
            domain = parsed.netloc.replace(".", "_")
            return f"{domain}_document.pdf"
        elif "text/html" in content_type or b"<html" in content[:200].lower():
            domain = parsed.netloc.replace(".", "_")
            return f"{domain}_webpage.html"

        return "downloaded_product_spec.pdf"


class PDFTableExtractor:
    """
    Extracts, cleans, and structures tables from PDF pages using pdfplumber.
    """

    @staticmethod
    def clean_cell(cell: Any) -> str:
        if cell is None:
            return ""
        # Replace line breaks and multiple spaces with a single space
        return re.sub(r'\s+', ' ', str(cell)).strip()

    @classmethod
    def extract_tables_from_page(cls, page) -> List[List[List[str]]]:
        """Extracts and normalizes all tables from a pdfplumber page."""
        raw_tables = page.extract_tables()
        cleaned_tables = []
        for table in (raw_tables or []):
            if not table or len(table) < 2:
                continue
            cleaned = []
            for row in table:
                cleaned_row = [cls.clean_cell(c) for c in row]
                # Keep row if at least one cell has content
                if any(cleaned_row):
                    cleaned.append(cleaned_row)
            if len(cleaned) >= 2:
                cleaned_tables.append(cleaned)
        return cleaned_tables

    @classmethod
    def table_to_markdown(cls, table: List[List[str]], max_rows: int = 40) -> str:
        """Converts a 2D table into standard Markdown table format."""
        if not table or len(table) < 2:
            return ""
        header = table[0]
        md_lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * len(header)) + " |"
        ]
        for row in table[1:max_rows]:
            # Pad row if shorter than header
            padded = row + [""] * (len(header) - len(row))
            md_lines.append("| " + " | ".join(padded[:len(header)]) + " |")
        return "\n".join(md_lines)

    @classmethod
    def extract_grade_rows(cls, table: List[List[str]]) -> List[Dict[str, str]]:
        """
        Extracts product grade items from product catalog tables where rows represent grades
        and columns represent technical properties.
        """
        if not table or len(table) < 2:
            return []
        
        header = [c.lower() for c in table[0]]
        results = []
        for row in table[1:]:
            first_cell = row[0].strip() if row else ""
            if not first_cell or len(first_cell) < 2:
                continue
            # Skip rows that are subheaders
            if any(h in first_cell.lower() for h in ["property", "method", "test condition", "unit", "typical value"]):
                continue

            row_details = []
            for i, val in enumerate(row[1:]):
                col_name = table[0][i+1] if i+1 < len(table[0]) else f"Col{i+1}"
                if val:
                    row_details.append(f"{col_name}: {val}")

            results.append({
                "grade": first_cell,
                "properties": "; ".join(row_details)
            })
        return results


class SingleSheetParser:
    """
    Parser for short technical datasheets (<= 5 pages, e.g. Lumicene 16AST15).
    Extracts all text and tables into 1 high-resolution ParsedProduct entry.
    """

    @classmethod
    def parse(cls, file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        full_text = ""
        markdown_tables = []
        default_name = os.path.splitext(filename)[0].replace("_", " ").title()

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                txt = page.extract_text() or ""
                if txt:
                    full_text += f"\n--- Page {page_num + 1} ---\n{txt}\n"
                
                tables = PDFTableExtractor.extract_tables_from_page(page)
                for t_idx, t in enumerate(tables):
                    md = PDFTableExtractor.table_to_markdown(t)
                    if md:
                        markdown_tables.append(f"### Table {t_idx + 1} (Page {page_num + 1}):\n{md}")

        clean_text = full_text.strip()
        tables_combined = "\n\n".join(markdown_tables)
        content_for_llm = f"DOCUMENT TEXT:\n{clean_text[:4000]}\n\nSPECIFICATION TABLES:\n{tables_combined[:4000]}"

        product_name = default_name
        feature_candidates = []

        try:
            from pipeline.utils.llm_client import chat_completion
            extraction_prompt = (
                "You are an expert product and materials specification analyst.\n"
                "Given this technical datasheet (including text and tabular properties), extract:\n"
                "1. The exact product/grade name.\n"
                "2. 6 to 10 specific technical features, processing characteristics, physical property limits (MFI, density, tensile), and target applications.\n"
                "Return JSON ONLY in this format:\n"
                "{\"product_name\": \"...\", \"category\": \"...\", \"features\": [\"...\", \"...\"]}"
            )
            msg = [
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": content_for_llm}
            ]
            llm_res = chat_completion(msg, model="gpt-4o-mini").strip()
            if llm_res.startswith("```"):
                llm_res = llm_res.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed_json = json.loads(llm_res)
            product_name = parsed_json.get("product_name") or default_name
            feature_candidates = parsed_json.get("features", [])
            category = parsed_json.get("category") or "Technical Specification"
        except Exception:
            lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
            product_name = lines[0][:80] if lines else default_name
            feature_candidates = [l for l in lines if 15 <= len(l) <= 150][:8]
            category = "Materials & Polymers"

        return [ParsedProduct(
            product_id=f"prod_{uuid.uuid4().hex[:8]}",
            product_name=str(product_name),
            category=str(category),
            features=feature_candidates[:14],
            full_text_snippet=(clean_text[:1500] + "\n\nTables:\n" + tables_combined[:1500]),
            source_filename=filename
        )]


class CatalogParser:
    """
    Parser for large multi-page product catalogs (> 5 pages up to 100+ pages,
    e.g. TotalEnergies European Product Range with 92 pages).
    
    1. Reads Table of Contents / Summary (pages 1-9) to identify major product lines.
    2. Extracts all product grade tables across the catalog.
    3. Groups grades by polymer/product families.
    4. Generates structured ParsedProduct entries for each family + key grade specs.
    """

    @classmethod
    def parse(cls, file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        default_name = os.path.splitext(filename)[0].replace("_", " ").title()

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            total_pages = len(pdf.pages)
            
            # 1. Extract Overview / Table of Contents from introductory pages (pages 1-9)
            toc_lines = []
            for p in range(min(9, total_pages)):
                txt = pdf.pages[p].extract_text() or ""
                for line in txt.split("\n"):
                    l = line.strip()
                    if l and len(l) > 4:
                        toc_lines.append(l)

            # 2. Extract tables across catalog pages
            grades_by_family: Dict[str, List[str]] = {}
            current_family = "Polymers & Specialty Grades"
            all_detected_grades = []

            for p_idx in range(min(9, total_pages), total_pages):
                page = pdf.pages[p_idx]
                page_txt = page.extract_text() or ""
                
                # Detect active section or family header on this page
                for line in page_txt.split("\n")[:4]:
                    clean_l = line.strip().upper()
                    if any(k in clean_l for k in ["POLYETHYLENE", "POLYPROPYLENE", "POLYSTYRENE", "RE:USE", "RE:BUILD", "RE:NEWABLE", "PIPES", "PACKAGING", "MEDICAL", "AUTOMOTIVE"]):
                        current_family = line.strip().title()
                        break

                tables = PDFTableExtractor.extract_tables_from_page(page)
                for table in tables:
                    grade_rows = PDFTableExtractor.extract_grade_rows(table)
                    for item in grade_rows:
                        grade_desc = f"{item['grade']} ({item['properties']})" if item['properties'] else item['grade']
                        all_detected_grades.append(grade_desc)
                        grades_by_family.setdefault(current_family, []).append(grade_desc)

        # 3. Formulate structured ParsedProduct entries
        products: List[ParsedProduct] = []

        # If we identified distinct families, create an entry for each major family
        if grades_by_family:
            for family_name, grade_list in grades_by_family.items():
                if not grade_list:
                    continue
                # Unique grades
                unique_grades = list(dict.fromkeys(grade_list))
                sample_features = unique_grades[:12]
                
                prod = ParsedProduct(
                    product_id=f"prod_{uuid.uuid4().hex[:8]}",
                    product_name=f"{default_name} - {family_name}",
                    category=family_name,
                    features=sample_features,
                    full_text_snippet=f"Catalog Section: {family_name}\nTotal Grades Identified: {len(unique_grades)}\nSample Grades & Properties:\n" + "\n".join(unique_grades[:20]),
                    source_filename=filename
                )
                products.append(prod)

        # Fallback or Master Catalog Summary entry
        if not products:
            products.append(ParsedProduct(
                product_id=f"prod_{uuid.uuid4().hex[:8]}",
                product_name=default_name,
                category="Industrial Product Catalog",
                features=[g for g in all_detected_grades[:14]],
                full_text_snippet="\n".join(toc_lines[:40]),
                source_filename=filename
            ))

        return products


class ProductDocumentService:
    """
    Unified facade to parse and extract structured product entries from:
    - Uploaded files (.pdf, .docx, .xlsx, .csv, .txt)
    - Web Links / URLs (direct PDF download links or webpage specifications)
    """

    @classmethod
    def parse_pdf(cls, file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        """Dynamically chooses SingleSheetParser or CatalogParser based on page count."""
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            page_count = len(reader.pages)
        except Exception:
            page_count = 1

        if page_count > 5:
            return CatalogParser.parse(file_bytes, filename)
        else:
            return SingleSheetParser.parse(file_bytes, filename)

    @classmethod
    def parse_docx(cls, file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        """Extracts text from Word doc (.docx) and structures it into product entries."""
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            return []

        default_name = os.path.splitext(filename)[0].replace("_", " ").title()
        product_name = paragraphs[0][:80] if len(paragraphs[0]) > 3 else default_name

        feature_candidates = []
        for p in paragraphs[1:]:
            if 15 <= len(p) <= 200:
                feature_candidates.append(p.lstrip("•-*▪► \t"))

        product = ParsedProduct(
            product_id=f"prod_{uuid.uuid4().hex[:8]}",
            product_name=product_name,
            features=feature_candidates[:12],
            full_text_snippet="\n".join(paragraphs)[:2000],
            source_filename=filename
        )
        return [product]

    @classmethod
    def parse_tabular(cls, file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        """Extracts products from CSV or Excel catalogues."""
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))

        col_map = {str(c).lower().strip(): c for c in df.columns}
        name_col = next((col_map[k] for k in ["product name", "product", "title", "name", "device", "model"] if k in col_map), df.columns[0])
        brand_col = next((col_map[k] for k in ["brand", "company", "manufacturer", "assignee", "vendor"] if k in col_map), None)
        category_col = next((col_map[k] for k in ["category", "type", "domain", "class"] if k in col_map), None)
        desc_col = next((col_map[k] for k in ["features", "description", "specification", "specs", "summary"] if k in col_map), None)

        products = []
        for _, row in df.iterrows():
            raw_name = str(row.get(name_col, "")).strip()
            if not raw_name or raw_name.lower() in ["nan", "none"]:
                continue

            features = []
            if desc_col and pd.notna(row.get(desc_col)):
                raw_desc = str(row[desc_col])
                features = [f.strip() for f in re.split(r'[,;|\n]', raw_desc) if len(f.strip()) > 3]

            products.append(ParsedProduct(
                product_id=f"prod_{uuid.uuid4().hex[:8]}",
                product_name=raw_name,
                brand_or_assignee=str(row[brand_col]).strip() if brand_col and pd.notna(row.get(brand_col)) else "Unknown",
                category=str(row[category_col]).strip() if category_col and pd.notna(row.get(category_col)) else "Uncategorized",
                features=features[:10],
                full_text_snippet=str(row.to_dict())[:1000],
                source_filename=filename
            ))
        return products

    @classmethod
    def parse_html(cls, html_bytes: bytes, filename: str, source_url: str = "") -> List[ParsedProduct]:
        """Extracts text and tables from an HTML product webpage."""
        soup = BeautifulSoup(html_bytes, "html.parser")
        
        # Remove script, style, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text().strip() if h1 else os.path.splitext(filename)[0].replace("_", " ").title()

        # Extract text paragraphs and table rows
        features = []
        for li in soup.find_all("li")[:20]:
            txt = li.get_text().strip()
            if 15 <= len(txt) <= 180:
                features.append(txt)

        # Extract tables from HTML
        for table in soup.find_all("table")[:3]:
            for tr in table.find_all("tr")[:15]:
                tds = [td.get_text().strip() for td in tr.find_all(["td", "th"])]
                if len(tds) >= 2 and any(tds):
                    features.append(": ".join(tds[:3]))

        clean_text = soup.get_text(separator=" ", strip=True)
        return [ParsedProduct(
            product_id=f"prod_{uuid.uuid4().hex[:8]}",
            product_name=title[:80],
            category="Web Specification",
            features=features[:12],
            full_text_snippet=clean_text[:2000],
            source_filename=source_url or filename
        )]

    @classmethod
    def parse_document(cls, filename: str, file_bytes: bytes, source_url: str = "") -> Tuple[List[ParsedProduct], Optional[str]]:
        """Main dispatcher for parsing files by extension."""
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext == ".pdf":
                return cls.parse_pdf(file_bytes, filename), None
            elif ext == ".docx":
                return cls.parse_docx(file_bytes, filename), None
            elif ext in [".csv", ".xlsx", ".xls"]:
                return cls.parse_tabular(file_bytes, filename), None
            elif ext in [".html", ".htm"]:
                return cls.parse_html(file_bytes, filename, source_url), None
            elif ext in [".txt", ".md"]:
                text = file_bytes.decode("utf-8", errors="ignore").strip()
                default_name = os.path.splitext(filename)[0].replace("_", " ").title()
                return [ParsedProduct(
                    product_id=f"prod_{uuid.uuid4().hex[:8]}",
                    product_name=default_name,
                    features=[line.strip() for line in text.split("\n") if len(line.strip()) > 10][:10],
                    full_text_snippet=text[:2000],
                    source_filename=filename
                )], None
            else:
                return [], f"Unsupported file type: {ext}"
        except Exception as e:
            return [], f"Error parsing {filename}: {str(e)}"

    @classmethod
    def parse_from_url(cls, url: str) -> Tuple[List[ParsedProduct], Optional[str]]:
        """Fetches a document or page from a URL and extracts products."""
        content, filename, content_type, err = URLFetcher.fetch_url(url)
        if err or not content:
            return [], err or "No content retrieved from URL."

        return cls.parse_document(filename, content, source_url=url)

    @classmethod
    def parse_from_urls(cls, urls: List[str]) -> Tuple[List[ParsedProduct], List[str]]:
        """Fetches multiple URLs and aggregates extracted products."""
        all_products = []
        errors = []
        for url in urls:
            cleaned = url.strip()
            if not cleaned:
                continue
            prods, err = cls.parse_from_url(cleaned)
            if err:
                errors.append(err)
            if prods:
                all_products.extend(prods)
        return all_products, errors
