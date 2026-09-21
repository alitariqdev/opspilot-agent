"""Incident triage agent for OpsPilot."""

import re
from typing import List, Set, Tuple

from src.opspilot.models import (
    EvidenceChunk,
    Incident,
    Severity,
    TimelineEvent,
    TriageResult,
)


def _extract_services_from_evidence(evidence_list: List[EvidenceChunk]) -> Set[str]:
    """Extract service names from evidence content.

    Args:
        evidence_list: List of evidence chunks

    Returns:
        Set of service names found in evidence
    """
    services: Set[str] = set()

    # Pattern to match [service-name] in logs or service-name in indexed content
    # Evidence content format: "TIMESTAMP LEVEL service message"
    service_pattern_brackets = re.compile(r"\[([a-z0-9-]+)\]")
    # Pattern for service name after timestamp and level (lowercase pattern)
    service_pattern_plain = re.compile(
        r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}z\s+\w+\s+([a-z0-9-]+)"
    )

    for evidence in evidence_list:
        # Skip runbook evidence for service extraction
        if evidence.source_type != "log":
            continue

        content_lower = evidence.content.lower()

        # Try bracketed pattern first
        matches = service_pattern_brackets.findall(content_lower)
        services.update(matches)

        # Try plain pattern (timestamp level service message)
        matches = service_pattern_plain.findall(content_lower)
        services.update(matches)

    return services


def _extract_symptoms_from_evidence(
    evidence_list: List[EvidenceChunk],
) -> List[str]:
    """Extract symptoms from evidence content.

    Args:
        evidence_list: List of evidence chunks

    Returns:
        List of symptom descriptions found in evidence
    """
    symptoms: List[str] = []
    seen_symptoms: Set[str] = set()

    # Look for error patterns and status codes
    error_keywords = [
        "503",
        "timeout",
        "failed",
        "error",
        "exhausted",
        "unavailable",
        "degraded",
    ]

    for evidence in evidence_list:
        content_lower = evidence.content.lower()

        # HTTP 503 errors
        if "503" in content_lower:
            symptom = "HTTP 503 Service Unavailable responses"
            if symptom not in seen_symptoms:
                symptoms.append(symptom)
                seen_symptoms.add(symptom)

        # Connection/pool issues
        if "pool exhausted" in content_lower or "connection" in content_lower and "timeout" in content_lower:
            symptom = "Database connection pool exhaustion"
            if symptom not in seen_symptoms:
                symptoms.append(symptom)
                seen_symptoms.add(symptom)

        # Timeout errors
        if "timeout" in content_lower and "timeout" not in seen_symptoms:
            symptom = "Request timeout errors"
            if symptom not in seen_symptoms:
                symptoms.append(symptom)
                seen_symptoms.add(symptom)

        # Failed operations
        if "failed" in content_lower or "error" in content_lower:
            if "operation failures" not in seen_symptoms:
                symptom = "Service operation failures"
                if symptom not in seen_symptoms:
                    symptoms.append(symptom)
                    seen_symptoms.add(symptom)

    return symptoms


def _extract_timestamps_from_content(content: str) -> List[str]:
    """Extract ISO 8601 timestamps from evidence content.

    Args:
        content: Evidence content text

    Returns:
        List of timestamp strings found
    """
    # Pattern for ISO 8601 timestamps
    timestamp_pattern = re.compile(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
    )
    return timestamp_pattern.findall(content)


def _build_timeline(
    evidence_list: List[EvidenceChunk],
) -> List[TimelineEvent]:
    """Build a chronological timeline from evidence.

    Args:
        evidence_list: List of evidence chunks

    Returns:
        List of timeline events sorted chronologically
    """
    events: List[TimelineEvent] = []

    for evidence in evidence_list:
        # Only build timeline from log evidence
        if evidence.source_type != "log":
            continue

        timestamps = _extract_timestamps_from_content(evidence.content)
        if not timestamps:
            continue

        timestamp = timestamps[0]  # Use first timestamp found
        content_lower = evidence.content.lower()

        # Extract service from [service] pattern or plain pattern
        service_match = re.search(r"\[([a-z0-9-]+)\]", content_lower)
        if not service_match:
            # Try plain pattern: TIMESTAMP LEVEL service message (lowercase)
            service_match = re.search(
                r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}z\s+\w+\s+([a-z0-9-]+)",
                content_lower,
            )
        service = service_match.group(1) if service_match else None

        # Create concise description based on content
        description = _create_event_description(evidence.content)

        if description:
            events.append(
                TimelineEvent(
                    timestamp=timestamp,
                    service=service,
                    description=description,
                    evidence_id=evidence.evidence_id,
                )
            )

    # Sort chronologically
    events.sort(key=lambda e: e.timestamp if e.timestamp else "")

    return events


def _create_event_description(content: str) -> str:
    """Create a concise event description from evidence content.

    Args:
        content: Evidence content

    Returns:
        Concise event description
    """
    content_lower = content.lower()

    # Match specific patterns
    if "pool exhausted" in content_lower:
        return "Connection pool exhausted"
    elif "503" in content_lower and "returned" in content_lower:
        return "Service returned HTTP 503"
    elif "timeout" in content_lower and "connection" in content_lower:
        return "Connection timeout detected"
    elif "long-running query" in content_lower:
        return "Long-running query detected"
    elif "failed to create" in content_lower:
        return "Operation failed"
    elif "health check failed" in content_lower:
        return "Health check failure"
    elif "executing query" in content_lower:
        return "Query execution started"
    elif "query execution completed" in content_lower:
        return "Query execution completed"
    elif "order created successfully" in content_lower:
        return "Service recovered - operation successful"

    # Generic description
    if "error" in content_lower:
        return "Error detected"
    elif "warn" in content_lower:
        return "Warning detected"
    elif "info" in content_lower:
        return "Status update"

    return "Event recorded"


def _assess_severity(
    evidence_list: List[EvidenceChunk],
    symptoms: List[str],
) -> Tuple[Severity, str]:
    """Assess incident severity based on evidence.

    Args:
        evidence_list: List of evidence chunks
        symptoms: List of symptoms extracted from evidence

    Returns:
        Tuple of (Severity level, rationale)
    """
    if not evidence_list:
        return Severity.SEV4, "Insufficient evidence for severity assessment"

    # Count critical indicators
    http_5xx_count = 0
    error_count = 0
    timeout_count = 0
    pool_exhausted_count = 0
    health_check_failures = 0

    for evidence in evidence_list:
        content_lower = evidence.content.lower()

        if "503" in content_lower:
            http_5xx_count += 1
        if "error" in content_lower and evidence.source_type == "log":
            error_count += 1
        if "timeout" in content_lower:
            timeout_count += 1
        if "pool exhausted" in content_lower:
            pool_exhausted_count += 1
        if "health check failed" in content_lower:
            health_check_failures += 1

    # SEV1: Widespread total outage indicators
    # (Not present in current evidence)

    # SEV2: Substantial user-facing degradation
    # Multiple 503 errors indicate user-facing service failures
    if http_5xx_count >= 3 or (pool_exhausted_count > 0 and http_5xx_count > 0):
        return (
            Severity.SEV2,
            f"Substantial user-facing degradation detected: {http_5xx_count} HTTP 503 responses, "
            f"connection pool exhaustion affecting core service",
        )

    # SEV3: Limited degradation
    if http_5xx_count > 0 or error_count >= 2:
        return (
            Severity.SEV3,
            f"Limited service degradation: {error_count} errors, {http_5xx_count} HTTP 5xx responses",
        )

    # SEV4: Informational or negligible impact
    return Severity.SEV4, "Minimal impact or insufficient evidence"


def _calculate_confidence(
    evidence_list: List[EvidenceChunk],
    timeline_events: List[TimelineEvent],
) -> float:
    """Calculate confidence score for triage assessment.

    Args:
        evidence_list: List of evidence chunks
        timeline_events: List of timeline events

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not evidence_list:
        return 0.0

    score = 0.0

    # Base confidence from evidence quantity
    if len(evidence_list) >= 5:
        score += 0.4
    elif len(evidence_list) >= 3:
        score += 0.3
    elif len(evidence_list) == 2:
        score += 0.15
    else:
        score += 0.1  # Single evidence: low base confidence

    # Bonus for timeline construction
    if timeline_events:
        score += 0.2

    # Bonus for log evidence (more concrete than runbook)
    log_evidence_count = sum(
        1 for e in evidence_list if e.source_type == "log"
    )
    if log_evidence_count >= 3:
        score += 0.2
    elif log_evidence_count > 0:
        score += 0.1

    # Bonus for multiple services (confirms scope)
    services = _extract_services_from_evidence(evidence_list)
    if len(services) >= 2:
        score += 0.1

    return min(score, 1.0)


class DemoTriageAgent:
    """Deterministic demo triage agent for offline operation.

    This agent performs evidence-grounded incident triage without
    making LLM calls or network requests. All conclusions are derived
    from the provided Incident and EvidenceChunk objects.
    """

    def triage(
        self,
        incident: Incident,
        evidence: List[EvidenceChunk],
    ) -> TriageResult:
        """Perform incident triage based on incident data and evidence.

        Args:
            incident: Incident object with metadata
            evidence: List of retrieved evidence chunks

        Returns:
            TriageResult with severity, timeline, and rationale

        Note:
            This is a deterministic implementation for demo mode.
            Does not claim root cause - only performs triage assessment.
        """
        # Handle empty evidence case
        if not evidence:
            return TriageResult(
                incident_id=incident.incident_id,
                severity=Severity.SEV4,
                affected_services=[],
                symptoms=[],
                timeline=[],
                rationale="Insufficient evidence provided for triage assessment",
                evidence_ids=[],
                confidence=0.0,
                insufficient_evidence=True,
                requires_human_review=True,
            )

        # Extract information from evidence
        affected_services = sorted(_extract_services_from_evidence(evidence))
        symptoms = _extract_symptoms_from_evidence(evidence)
        timeline = _build_timeline(evidence)
        evidence_ids = [e.evidence_id for e in evidence]

        # Assess severity
        severity, severity_rationale = _assess_severity(evidence, symptoms)

        # Calculate confidence
        confidence = _calculate_confidence(evidence, timeline)

        # Build comprehensive rationale
        rationale = self._build_rationale(
            severity_rationale,
            affected_services,
            symptoms,
            timeline,
        )

        # Determine if human review is needed
        requires_human_review = (
            severity in [Severity.SEV1, Severity.SEV2]
            or confidence < 0.5
        )

        return TriageResult(
            incident_id=incident.incident_id,
            severity=severity,
            affected_services=affected_services,
            symptoms=symptoms,
            timeline=timeline,
            rationale=rationale,
            evidence_ids=evidence_ids,
            confidence=confidence,
            insufficient_evidence=len(evidence) < 3,
            requires_human_review=requires_human_review,
        )

    def _build_rationale(
        self,
        severity_rationale: str,
        affected_services: List[str],
        symptoms: List[str],
        timeline: List[TimelineEvent],
    ) -> str:
        """Build a comprehensive rationale for the triage assessment.

        Args:
            severity_rationale: Severity-specific rationale
            affected_services: List of affected services
            symptoms: List of symptoms
            timeline: Timeline events

        Returns:
            Comprehensive rationale string
        """
        parts = [severity_rationale]

        if affected_services:
            parts.append(
                f"Affected services: {', '.join(affected_services)}."
            )

        if symptoms:
            parts.append(
                f"Key symptoms: {'; '.join(symptoms)}."
            )

        if timeline:
            parts.append(
                f"Timeline contains {len(timeline)} documented events."
            )

        parts.append(
            "Note: This is a triage assessment only. "
            "Root cause analysis requires further investigation."
        )

        return " ".join(parts)
