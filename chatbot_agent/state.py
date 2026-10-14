"""
State definitions for the Chatbot Agent.

Mirrors the pattern used in taxonomy_builder/state.py.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


# ---------------------------------------------------------------------------
# Intent Enum
# ---------------------------------------------------------------------------

class ChatIntent(str, Enum):
    BUILD_TAXONOMY   = "build_taxonomy"    # "Build taxonomy from this"
    CUSTOM_MAPPING   = "custom_mapping"    # "Map X under Y"
    EXPLAIN_NODE     = "explain_node"      # "Why is X here?"
    CORRECT_NODE     = "correct_node"      # "X grouping is wrong"
    RE_RUN           = "re_run"            # "Rebuild with corrections"
    GENERAL_QUESTION = "general_question"  # Anything else


# ---------------------------------------------------------------------------
# Message Schema
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    model_config = {"extra": "allow"}
    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(description="Message text or structured JSON string")
    intent: Optional[str] = Field(default=None, description="Detected intent for user messages")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra data (e.g. product card, run_id)")
    timestamp: Optional[str] = Field(default=None, description="Message timestamp")


# ---------------------------------------------------------------------------
# Product Understanding (extracted by ingest_product node)
# ---------------------------------------------------------------------------

class ProductUnderstanding(BaseModel):
    model_config = {"extra": "allow"}
    product_name: str = Field(description="Name of the product")
    domain: str = Field(description="Primary technology domain")
    key_features: list[str] = Field(description="Key technical features / claims")
    target_industry: str = Field(description="Target industry or application area")
    relevant_patent_classes: list[str] = Field(default_factory=list, description="IPC/CPC patent classes")
    focus_areas: list[str] = Field(description="Technology areas to prioritize in taxonomy")
    avoid_areas: list[str] = Field(default_factory=list, description="Technology areas NOT relevant")
    summary: str = Field(description="2-3 sentence human-readable summary for the user")


# ---------------------------------------------------------------------------
# Mapping Rule (user-defined, e.g. "Map X under Y")
# ---------------------------------------------------------------------------

class MappingRuleType(str, Enum):
    REPARENT   = "reparent"    # Move node X under node Y
    MERGE      = "merge"       # Combine X and Y into one node
    SPLIT      = "split"       # Split X into X1 and X2
    RENAME     = "rename"      # Rename node X to Z
    EXCLUDE    = "exclude"     # Remove node X from taxonomy
    PRIORITIZE = "prioritize"  # Weight X more heavily

class MappingRule(BaseModel):
    model_config = {"extra": "allow"}
    rule_type: MappingRuleType
    source_node: str = Field(description="The node being acted upon")
    target_node: Optional[str] = Field(default=None, description="Target parent / merge target / new name")
    applied: bool = Field(default=False, description="Whether this rule has been applied to a run")
    raw_instruction: str = Field(description="Original user text that generated this rule")


# ---------------------------------------------------------------------------
# Chatbot Agent State (input/output for the graph)
# ---------------------------------------------------------------------------

class ChatAgentState(BaseModel):
    """
    Full state passed through the chatbot LangGraph graph.
    Populated incrementally as nodes execute.
    """
    model_config = {"extra": "allow"}

    # ── Session identity ─────────────────────────────────────────────────────
    session_id: str
    run_id: Optional[str] = None           # Linked taxonomy run (post-run phase)

    # ── Conversation history ──────────────────────────────────────────────────
    messages: list[ChatMessage] = Field(default_factory=list)

    # ── Latest user input ─────────────────────────────────────────────────────
    user_message: str = ""

    # ── Detected intent for current turn ──────────────────────────────────────
    detected_intent: Optional[ChatIntent] = None
    intent_entities: dict[str, Any] = Field(default_factory=dict)

    # ── Product ingestion ──────────────────────────────────────────────────────
    product_doc_text: Optional[str] = None        # Raw extracted text from uploaded doc
    mental_model: Optional[ProductUnderstanding] = None   # LLM-extracted understanding
    mental_model_confirmed: bool = False           # User confirmed the mental model

    # ── Mapping rules ──────────────────────────────────────────────────────────
    mapping_rules: list[MappingRule] = Field(default_factory=list)

    # ── Taxonomy context (post-run) ────────────────────────────────────────────
    final_taxonomy: Optional[list[dict[str, Any]]] = None
    source_data: Optional[dict[str, Any]] = None

    # ── Response to send back ──────────────────────────────────────────────────
    response_text: str = ""
    response_metadata: dict[str, Any] = Field(default_factory=dict)  # e.g. product card, run trigger

    # ── Errors ────────────────────────────────────────────────────────────────
    errors: list[str] = Field(default_factory=list)
