import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.declarative import declarative_base
from urllib.parse import urlparse

raw_url = os.environ.get("DATABASE_URL", "postgresql://postgres:wissen67@localhost:5432/taxonomy_db")
if raw_url.endswith("/"):
    raw_url += "taxonomy_db"

DATABASE_URL = raw_url

# Auto-create script removed for production deployment

# If we changed host to localhost for DB creation, let's also update the engine URL for SQLAlchemy
if not os.environ.get("IN_DOCKER"):
    DATABASE_URL = DATABASE_URL.replace("@postgres:5432", "@localhost:5432")
    DATABASE_URL = DATABASE_URL.replace("@host.docker.internal:5432", "@localhost:5432")

# SQLAlchemy needs the dialect specified explicitly in modern versions if using psycopg2
engine_url = DATABASE_URL
if engine_url.startswith("postgresql://"):
    engine_url = engine_url.replace("postgresql://", "postgresql+psycopg2://")

engine = create_engine(engine_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
