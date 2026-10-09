# pyrefly: ignore [missing-import]
from sqlalchemy import Column, String, Boolean, DateTime, Integer
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
