"""Data models for OpsPilot."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Incident(BaseModel):
    """Represents a software incident requiring diagnosis.

    Attributes:
        incident_id: Unique identifier for the incident
        title: Brief summary of the incident
        description: Detailed description of the incident
        symptoms: List of observed symptoms
        start_time: When the incident began (ISO 8601 format)
        affected_services: Services impacted by the incident
        severity: Incident severity level
        status: Current incident status
    """

    incident_id: str = Field(description="Unique incident identifier")
    title: str = Field(description="Incident title")
    description: str = Field(description="Detailed incident description")
    symptoms: List[str] = Field(default_factory=list, description="Observed symptoms")
    start_time: str = Field(description="Incident start time (ISO 8601)")
    affected_services: List[str] = Field(
        default_factory=list, description="Affected services"
    )
    severity: str = Field(description="Incident severity")
    status: str = Field(description="Incident status")


class LogEntry(BaseModel):
    """Represents a parsed log entry.

    Attributes:
        timestamp: Log entry timestamp
        level: Log level (INFO, WARN, ERROR, DEBUG, etc.)
        service: Service that generated the log entry
        message: Log message content
        source_file: Original log file name
        line_number: Line number in the source file
    """

    timestamp: str = Field(description="Log timestamp (ISO 8601)")
    level: str = Field(description="Log level")
    service: str = Field(description="Service name")
    message: str = Field(description="Log message")
    source_file: str = Field(description="Source log file")
    line_number: int = Field(description="Line number in source file")


class EvidenceChunk(BaseModel):
    """Represents a piece of evidence retrieved for incident diagnosis.

    Attributes:
        evidence_id: Stable unique identifier for this evidence
        source_file: Filename where evidence originated
        source_type: Type of evidence source (log, runbook, etc.)
        line_number: Line number in the source file
        content: The evidence content/text
        score: Retrieval relevance score
        metadata: Optional additional metadata
    """

    evidence_id: str = Field(description="Unique evidence identifier")
    source_file: str = Field(description="Source filename")
    source_type: str = Field(description="Evidence source type")
    line_number: int = Field(description="Line number in source")
    content: str = Field(description="Evidence content")
    score: float = Field(description="Retrieval relevance score")
    metadata: Optional[dict] = Field(
        default=None, description="Additional metadata"
    )
