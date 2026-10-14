"""
Chatbot Agent — Conversational AI layer for the Taxonomy Builder.

Structure:
  chatbot_agent/
  ├── state.py          — Chat session state & message schemas
  ├── graph.py          — LangGraph graph for intent routing
  ├── nodes/
  │   ├── ingest_product.py   — Parse & LLM-understand uploaded product docs
  │   ├── detect_intent.py    — Classify user message intent
  │   ├── respond_general.py  — General Q&A responses
  │   ├── build_taxonomy_cmd.py — "Build taxonomy" command handler
  │   ├── apply_mapping_cmd.py  — "Map X under Y" command handler
  │   └── explain_taxonomy.py   — Post-run RAG Q&A on generated taxonomy
  └── utils/
      ├── doc_parser.py       — PDF/DOCX/text extraction utilities
      └── rag_retriever.py    — Keyword/semantic search over taxonomy nodes
"""
