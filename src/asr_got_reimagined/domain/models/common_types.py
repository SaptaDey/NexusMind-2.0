"""
Common type definitions to avoid circular imports.
Provides type definitions used across multiple modules.
"""

from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class GoTProcessorSessionData(BaseModel):
    """Data model for session data maintained by GoTProcessor."""

    session_id: str = Field(default_factory=lambda: f"session-{uuid.uuid4()}")
    query: str
    graph_state: Optional[Any] = None
    final_answer: Optional[str] = None
    final_confidence_vector: List[float] = Field(default=[0.5, 0.5, 0.5, 0.5])
    accumulated_context: Dict[str, Any] = Field(default_factory=dict)
    stage_outputs_trace: List[Dict[str, Any]] = Field(default_factory=list)


class ComposedOutput(BaseModel):
    """Model for the output structure from the Composition Stage."""

    executive_summary: str
    detailed_report: Optional[str] = None
    key_findings: List[str] = Field(default_factory=list)
    confidence_assessment: Optional[Dict[str, Any]] = None
