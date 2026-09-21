"""Data models for OpsPilot."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


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


class Severity(str, Enum):
    """Incident severity levels.

    SEV1: Critical - widespread outage, data loss, severe security/safety impact
    SEV2: High - substantial user-facing degradation, repeated 5xx errors
    SEV3: Medium - limited degradation, intermittent errors
    SEV4: Low - informational, negligible impact, insufficient evidence
    """

    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class TimelineEvent(BaseModel):
    """Represents a single event in the incident timeline.

    Attributes:
        timestamp: Event timestamp (ISO 8601) if available from evidence
        service: Service involved in this event if available from evidence
        description: Concise event description
        evidence_id: ID of the evidence supporting this event
    """

    timestamp: Optional[str] = Field(
        default=None, description="Event timestamp (ISO 8601)"
    )
    service: Optional[str] = Field(
        default=None, description="Service involved in event"
    )
    description: str = Field(description="Event description")
    evidence_id: str = Field(description="Supporting evidence ID")


class TriageResult(BaseModel):
    """Result of incident triage assessment.

    Attributes:
        incident_id: ID of the incident being triaged
        severity: Assessed severity level
        affected_services: List of services affected (from evidence)
        symptoms: List of observed symptoms (from evidence)
        timeline: Chronological timeline of events with evidence
        rationale: Explanation of the triage assessment
        evidence_ids: List of all evidence IDs used in assessment
        confidence: Confidence score between 0.0 and 1.0
        insufficient_evidence: True if evidence is insufficient for assessment
        requires_human_review: True if human review is recommended
    """

    incident_id: str = Field(description="Incident identifier")
    severity: Severity = Field(description="Assessed severity")
    affected_services: List[str] = Field(
        default_factory=list, description="Affected services from evidence"
    )
    symptoms: List[str] = Field(
        default_factory=list, description="Observed symptoms from evidence"
    )
    timeline: List[TimelineEvent] = Field(
        default_factory=list, description="Chronological timeline with evidence"
    )
    rationale: str = Field(description="Triage rationale")
    evidence_ids: List[str] = Field(
        default_factory=list, description="All evidence IDs used"
    )
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    insufficient_evidence: bool = Field(
        default=False, description="True if evidence is insufficient"
    )
    requires_human_review: bool = Field(
        default=False, description="True if human review recommended"
    )


class HypothesisStatus(str, Enum):
    """Status of a root cause hypothesis after verification.

    supported: Evidence strongly supports the hypothesis
    partially_supported: Some supporting evidence, gaps remain
    unsupported: Evidence does not support the hypothesis
    """

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"


class RootCauseHypothesis(BaseModel):
    """Represents a root cause hypothesis for an incident.

    Attributes:
        hypothesis_id: Unique identifier for this hypothesis
        title: Brief title summarizing the hypothesis
        description: Detailed description of the hypothesized root cause
        rank: Ranking position (1 = most likely)
        confidence: Confidence score between 0.0 and 1.0
        evidence_ids: List of evidence IDs supporting this hypothesis
        reasoning: Explanation of why this hypothesis is plausible
        status: Verification status (after verification)
        missing_evidence: Evidence gaps that would strengthen hypothesis
        requires_human_review: True if human review is needed
    """

    hypothesis_id: str = Field(description="Unique hypothesis identifier")
    title: str = Field(description="Brief hypothesis title")
    description: str = Field(description="Detailed hypothesis description")
    rank: int = Field(description="Ranking position", ge=1)
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    evidence_ids: List[str] = Field(
        default_factory=list, description="Supporting evidence IDs"
    )
    reasoning: str = Field(description="Reasoning for this hypothesis")
    status: Optional[HypothesisStatus] = Field(
        default=None, description="Verification status"
    )
    missing_evidence: List[str] = Field(
        default_factory=list, description="Missing evidence descriptions"
    )
    requires_human_review: bool = Field(
        default=True, description="Human review required"
    )


class DiagnosisResult(BaseModel):
    """Result of incident diagnosis producing root cause hypotheses.

    Attributes:
        incident_id: ID of the incident being diagnosed
        hypotheses: List of root cause hypotheses, ranked by confidence
        summary: Summary of the diagnosis
        limitations: Known limitations or gaps in the diagnosis
        insufficient_evidence: True if evidence is insufficient for diagnosis
        requires_human_review: True if human review is required
    """

    incident_id: str = Field(description="Incident identifier")
    hypotheses: List[RootCauseHypothesis] = Field(
        default_factory=list, description="Root cause hypotheses, ranked"
    )
    summary: str = Field(description="Diagnosis summary")
    limitations: List[str] = Field(
        default_factory=list, description="Known limitations"
    )
    insufficient_evidence: bool = Field(
        default=False, description="True if evidence insufficient"
    )
    requires_human_review: bool = Field(
        default=True, description="Human review required"
    )


class VerificationResult(BaseModel):
    """Result of hypothesis verification against evidence.

    Attributes:
        incident_id: ID of the incident
        verified_hypotheses: Hypotheses that passed verification
        rejected_hypothesis_ids: IDs of hypotheses rejected during verification
        verification_summary: Summary of verification findings
        requires_human_review: True if human review required
    """

    incident_id: str = Field(description="Incident identifier")
    verified_hypotheses: List[RootCauseHypothesis] = Field(
        default_factory=list, description="Verified hypotheses"
    )
    rejected_hypothesis_ids: List[str] = Field(
        default_factory=list, description="Rejected hypothesis IDs"
    )
    verification_summary: str = Field(description="Verification summary")
    requires_human_review: bool = Field(
        default=True, description="Human review required"
    )


class RiskLevel(str, Enum):
    """Risk level for remediation actions.

    LOW: Minimal risk, reversible, read-only or monitoring actions
    MEDIUM: Moderate risk, configuration changes, service restarts
    HIGH: High risk, data changes, production database operations
    CRITICAL: Critical risk, destructive operations, requires change control
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationAction(BaseModel):
    """Represents a single remediation action recommendation.

    Attributes:
        action_id: Unique identifier for this action
        title: Brief title for the action
        description: Detailed description of the action
        rationale: Why this action is recommended
        priority: Priority rank (1 = highest priority)
        risk_level: Risk level of this action
        category: Action category (investigation, containment, recovery, prevention)
        supporting_evidence_ids: Evidence supporting this recommendation
        requires_human_approval: True if human approval required before execution
        validation_step: How to validate the action was effective
        rollback_consideration: How to rollback if action causes issues
    """

    action_id: str = Field(description="Unique action identifier")
    title: str = Field(description="Action title")
    description: str = Field(description="Detailed action description")
    rationale: str = Field(description="Rationale for this action")
    priority: int = Field(description="Priority rank (1 = highest)", ge=1)
    risk_level: RiskLevel = Field(description="Risk level")
    category: str = Field(description="Action category")
    supporting_evidence_ids: List[str] = Field(
        default_factory=list, description="Supporting evidence IDs"
    )
    requires_human_approval: bool = Field(
        default=True, description="Human approval required"
    )
    validation_step: str = Field(description="How to validate effectiveness")
    rollback_consideration: str = Field(
        description="How to rollback if needed"
    )


class RemediationPlan(BaseModel):
    """Complete remediation plan for an incident.

    Attributes:
        incident_id: ID of the incident
        actions: List of recommended actions, ordered by priority
        summary: Summary of the remediation plan
        limitations: Known limitations or constraints
        requires_human_approval: True if any action requires human approval
    """

    incident_id: str = Field(description="Incident identifier")
    actions: List[RemediationAction] = Field(
        default_factory=list, description="Recommended actions, ordered by priority"
    )
    summary: str = Field(description="Remediation plan summary")
    limitations: List[str] = Field(
        default_factory=list, description="Plan limitations"
    )
    requires_human_approval: bool = Field(
        default=True, description="Human approval required"
    )
