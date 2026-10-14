import os
import uuid
import re
import json
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
# pyrefly: ignore [missing-import]
import pypdf
# pyrefly: ignore [missing-import]
import docx
# pyrefly: ignore [missing-import]
from product_schemas import ParsedProduct

class ProductDocumentService:
    """
    Service to parse and extract structured product information from 
    uploaded documents (.pdf, .docx, .xlsx, .csv, .txt).
    """

    @staticmethod
    def parse_pdf(file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        """Extracts text from PDF and structures it into product entries."""
        import io
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        clean_text = full_text.strip()
        if not clean_text:
            return []

        # Derive a human-friendly product title from filename or document content
        default_name = os.path.splitext(filename)[0].replace("_", " ").title()
        lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
        
        product_name = default_name
        feature_candidates = []

        try:
            from pipeline.utils.llm_client import chat_completion
            extraction_prompt = (
                "You are an expert product and technical document analyst.\n"
                "Given this document text, extract:\n"
                "1. The exact product name, drug name, or main subject title.\n"
                "2. 5 to 8 specific technical features, mechanisms of action, or hardware/chemical specifications.\n"
                "Return JSON ONLY:\n"
                "{\"product_name\": \"...\", \"features\": [\"...\", \"...\"]}"
            )
            msg = [
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": clean_text[:3500]}
            ]
            llm_res = chat_completion(msg, model="gpt-4o-mini").strip()
            if llm_res.startswith("```"):
                llm_res = llm_res.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed_json = json.loads(llm_res)
            product_name = parsed_json.get("product_name") or default_name
            feature_candidates = parsed_json.get("features", [])
        except Exception:
            # Fallback to heuristic parsing if LLM is unavailable
            first_meaningful_line = lines[0] if lines else default_name
            product_name = first_meaningful_line[:80] if len(first_meaningful_line) > 3 else default_name
            sentences = re.split(r'[.;]\s+', clean_text)
            feature_candidates = [s.strip() for s in sentences if 15 <= len(s) <= 150][:8]

        product = ParsedProduct(
            product_id=f"prod_{uuid.uuid4().hex[:8]}",
            product_name=str(product_name),
            features=feature_candidates[:12],
            full_text_snippet=clean_text[:2000],
            source_filename=filename
        )
        return [product]

    @staticmethod
    def parse_docx(file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        """Extracts text from Word doc (.docx) and structures it into product entries."""
        import io
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

    @staticmethod
    def parse_tabular(file_bytes: bytes, filename: str) -> List[ParsedProduct]:
        """Extracts products from CSV or Excel catalogues."""
        import io
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))

        # Normalize column headers
        col_map = {str(c).lower().strip(): c for c in df.columns}
        
        # Identify name column
        name_col = next((col_map[k] for k in ["product name", "product", "title", "name", "device", "model"] if k in col_map), df.columns[0])
        brand_col = next((col_map[k] for k in ["brand", "company", "manufacturer", "assignee", "vendor"] if k in col_map), None)
        category_col = next((col_map[k] for k in ["category", "type", "domain", "class"] if k in col_map), None)
        desc_col = next((col_map[k] for k in ["features", "description", "specification", "specs", "summary"] if k in col_map), None)

        products = []
        for _, row in df.iterrows():
            raw_name = str(row.get(name_col, "")).strip()
            if not raw_name or raw_name.lower() in ["nan", "none"]:
                continue

            # Extract features from description column or remaining columns
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
    def parse_document(cls, filename: str, file_bytes: bytes) -> Tuple[List[ParsedProduct], Optional[str]]:
        """Dispatcher that routes file to the right parser based on extension."""
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext == ".pdf":
                return cls.parse_pdf(file_bytes, filename), None
            elif ext == ".docx":
                return cls.parse_docx(file_bytes, filename), None
            elif ext in [".csv", ".xlsx", ".xls"]:
                return cls.parse_tabular(file_bytes, filename), None
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
