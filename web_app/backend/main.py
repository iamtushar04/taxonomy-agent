import os
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from database import engine, Base

# Import modular package routers
# pyrefly: ignore [missing-import]
from routes.taxonomy import router as api_router
# pyrefly: ignore [missing-import]
from routes.products import router as product_router
# pyrefly: ignore [missing-import]
from routes.chat import router as chat_router

# Create database tables
Base.metadata.create_all(bind=engine)

# Use the reliable built-in FastAPI docs
app = FastAPI(title="Taxonomy Builder API")

# Allow the React frontend to talk to this API
frontend_url = os.environ.get("FRONTEND_URL", "*")
origins = [url.strip() for url in frontend_url.split(",")] if frontend_url != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Include all the API routes
app.include_router(api_router)
app.include_router(product_router)
app.include_router(chat_router)

# Reload trigger: 2026-10-14 19:18 IST - Multi-product carousel list attached in analyze_product
