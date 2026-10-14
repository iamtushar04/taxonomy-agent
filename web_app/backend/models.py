# pyrefly: ignore [missing-import]
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import JSONB
# pyrefly: ignore [missing-import]
from database import Base
import datetime

class Run(Base):
    __tablename__ = "runs"
    
    id = Column(String, primary_key=True, index=True)
    status = Column(String, default="pending")
    input_ids = Column(JSONB, default=list)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Store results inline instead of complex relations
    is_pubmed = Column(Boolean, default=False)
    final_taxonomy = Column(JSONB, nullable=True)
    source_data = Column(JSONB, nullable=True)
    user_id = Column(Integer, index=True)
    name = Column(String, nullable=True)


class ChatSession(Base):
    """
    Stores a chatbot conversation session.
    Linked to a Run after taxonomy generation; nullable before.
    """
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)   # UUID
    user_id = Column(Integer, index=True, nullable=False)
    run_id = Column(String, nullable=True, index=True)  # Linked after run starts

    # Product document (raw text extracted from upload)
    product_doc_text = Column(Text, nullable=True)

    # LLM-extracted product understanding (ProductUnderstanding as JSON)
    mental_model = Column(JSONB, nullable=True)
    mental_model_confirmed = Column(Boolean, default=False)

    # User-defined mapping rules (list of MappingRule as JSON)
    mapping_rules = Column(JSONB, default=list)

    # Full conversation history [{role, content, intent, metadata, timestamp}]
    messages = Column(JSONB, default=list)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
