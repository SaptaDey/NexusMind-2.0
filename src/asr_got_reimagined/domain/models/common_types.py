"""
Common type definitions to avoid circular imports.
Provides type definitions used across multiple modules.
"""

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class GoTProcessorSessionData(BaseModel):
    """Data model for session data maintained by GoTProcessor."""

    session_id: str = Field(default_factory=lambda: f"session-{uuid.uuid4()}")
    query: str
    graph_state: Optional[Any] = None
    final_answer: Optional[str] = None
    final_confidence_vector: list[float] = Field(default=[0.5, 0.5, 0.5, 0.5])
    accumulated_context: dict[str, Any] = Field(default_factory=dict)
    stage_outputs_trace: list[dict[str, Any]] = Field(default_factory=list)


class ComposedOutput(BaseModel):
    """Model for the output structure from the Composition Stage."""

    executive_summary: str
    detailed_report: Optional[str] = None
    key_findings: list[str] = Field(default_factory=list)
    confidence_assessment: Optional[dict[str, Any]] = None
