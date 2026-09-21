"""Root cause diagnosis agent for OpsPilot."""

import hashlib
import re
from typing import List, Set, Tuple

from src.opspilot.models import (
    DiagnosisResult,
    EvidenceChunk,
    Incident,
    RootCauseHypothesis,
    TriageResult,
)


def _generate_hypothesis_id(title: str, rank: int) -> str:
    """Generate a stable hypothesis ID.

    Args:
        title: Hypothesis title
        rank: Hypothesis rank

    Returns:
        Stable hypothesis identifier
    """
    content = f"{title}:{rank}"
    hash_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"hyp_{hash_digest[:16]}"


def _extract_evidence_patterns(evidence_list: List[EvidenceChunk]) -> dict:
    """Extract evidence patterns for hypothesis generation.

    Args:
        evidence_list: List of evidence chunks

    Returns:
        Dictionary of pattern counts and details
    """
    patterns = {
        "pool_exhaustion": [],
        "long_running_queries": [],
        "http_5xx": [],
        "timeouts": [],
        "service_failures": [],
        "resource_saturation": [],
    }

    for evidence in evidence_list:
        content_lower = evidence.content.lower()

        # Connection pool exhaustion
        if "pool exhausted" in content_lower or (
            "connection" in content_lower and "pool" in content_lower
        ):
            patterns["pool_exhaustion"].append(evidence.evidence_id)

        # Long-running queries
        if (
            "long-running query" in content_lower
            or "duration" in content_lower
            and "query" in content_lower
        ):
            patterns["long_running_queries"].append(evidence.evidence_id)

        # HTTP 5xx errors
        if "503" in content_lower or "500" in content_lower or "502" in content_lower:
            patterns["http_5xx"].append(evidence.evidence_id)

        # Timeouts
        if "timeout" in content_lower:
            patterns["timeouts"].append(evidence.evidence_id)

        # Service failures
        if "failed" in content_lower or "failure" in content_lower:
            patterns["service_failures"].append(evidence.evidence_id)

        # Resource saturation (CPU, memory, connections)
        if (
            "100%" in content_lower
            or "saturated" in content_lower
            or ("active" in content_lower and "/" in content_lower)
        ):
            patterns["resource_saturation"].append(evidence.evidence_id)

    return patterns


def _detect_causal_sequence(
    patterns: dict, evidence_list: List[EvidenceChunk]
) -> List[str]:
    """Detect potential causal sequences in evidence.

    Args:
        patterns: Evidence patterns dictionary
        evidence_list: Original evidence list

    Returns:
        List of observed causal sequence descriptions
    """
    sequences = []

    # Long-running query → pool exhaustion → service failures
    if (
        patterns["long_running_queries"]
        and patterns["pool_exhaustion"]
        and patterns["service_failures"]
    ):
        sequences.append(
            "Long-running database activity preceded connection pool exhaustion, "
            "which was followed by service failures"
        )

    # Pool exhaustion → timeouts → HTTP errors
    if (
        patterns["pool_exhaustion"]
        and patterns["timeouts"]
        and patterns["http_5xx"]
    ):
        sequences.append(
            "Connection pool exhaustion correlated with timeouts and HTTP 5xx responses"
        )

    # Resource saturation → service degradation
    if patterns["resource_saturation"] and patterns["service_failures"]:
        sequences.append("Resource saturation observed alongside service failures")

    return sequences


def _generate_hypothesis_pool_exhaustion(
    patterns: dict, sequences: List[str], rank: int
) -> RootCauseHypothesis:
    """Generate hypothesis for database connection pool exhaustion.

    Args:
        patterns: Evidence patterns
        sequences: Causal sequences
        rank: Hypothesis rank

    Returns:
        Root cause hypothesis
    """
    title = "Database connection pool exhaustion caused service unavailability"

    # Gather supporting evidence
    evidence_ids = list(
        set(
            patterns["pool_exhaustion"]
            + patterns["timeouts"]
            + patterns["http_5xx"][:3]
        )
    )

    # Calculate confidence based on evidence strength
    confidence = 0.5  # Base confidence
    if len(patterns["pool_exhaustion"]) >= 2:
        confidence += 0.2
    if patterns["timeouts"]:
        confidence += 0.1
    if patterns["http_5xx"]:
        confidence += 0.1
    if sequences:
        confidence += 0.1

    confidence = min(confidence, 0.95)

    description = (
        "The database connection pool reached its maximum capacity, preventing "
        "the order service from acquiring connections to process requests. "
        "This resulted in connection timeout errors and HTTP 503 responses."
    )

    reasoning = (
        f"Evidence shows {len(patterns['pool_exhaustion'])} instances of pool exhaustion, "
        f"{len(patterns['timeouts'])} timeout events, and "
        f"{len(patterns['http_5xx'])} HTTP 5xx responses. "
    )

    if sequences:
        reasoning += f"Causal sequence observed: {sequences[0]}. "

    reasoning += (
        "However, this diagnosis is correlational; the root cause of pool "
        "exhaustion requires further investigation."
    )

    missing_evidence = []
    if not patterns["long_running_queries"]:
        missing_evidence.append(
            "Evidence of what consumed the database connections"
        )
    missing_evidence.append("Database server resource utilization metrics")
    missing_evidence.append("Connection pool configuration details")

    return RootCauseHypothesis(
        hypothesis_id=_generate_hypothesis_id(title, rank),
        title=title,
        description=description,
        rank=rank,
        confidence=confidence,
        evidence_ids=evidence_ids,
        reasoning=reasoning,
        missing_evidence=missing_evidence,
        requires_human_review=True,
    )


def _generate_hypothesis_long_running_query(
    patterns: dict, evidence_list: List[EvidenceChunk], rank: int
) -> RootCauseHypothesis:
    """Generate hypothesis for long-running query causing pool exhaustion.

    Args:
        patterns: Evidence patterns
        evidence_list: Full evidence list
        rank: Hypothesis rank

    Returns:
        Root cause hypothesis
    """
    title = "Long-running database query exhausted connection pool"

    evidence_ids = list(
        set(
            patterns["long_running_queries"]
            + patterns["pool_exhaustion"][:2]
            + patterns["http_5xx"][:2]
        )
    )

    # Higher confidence if we have direct evidence of long-running query
    confidence = 0.6 if patterns["long_running_queries"] else 0.3

    if len(patterns["long_running_queries"]) >= 1:
        confidence += 0.15
    if len(patterns["pool_exhaustion"]) >= 2:
        confidence += 0.1
    if patterns["http_5xx"]:
        confidence += 0.05

    confidence = min(confidence, 0.90)

    # Extract query details if available
    query_details = ""
    for eid in patterns["long_running_queries"]:
        for evidence in evidence_list:
            if evidence.evidence_id == eid:
                if "duration" in evidence.content.lower():
                    query_details = (
                        f"Evidence shows a query with extended duration. "
                    )
                break

    description = (
        "A database query ran for an extended period, holding database connections "
        "and preventing other operations from acquiring connections. "
        f"{query_details}"
        "This led to connection pool exhaustion and subsequent service failures."
    )

    reasoning = (
        f"Evidence includes {len(patterns['long_running_queries'])} reference(s) to "
        f"long-running queries and {len(patterns['pool_exhaustion'])} instances of "
        "pool exhaustion. Temporal correlation suggests the query may have "
        "contributed to pool exhaustion, though causality is not definitively established."
    )

    missing_evidence = [
        "Query execution plan and optimization details",
        "Application or service that initiated the query",
        "Whether the query was terminated or completed naturally",
    ]

    return RootCauseHypothesis(
        hypothesis_id=_generate_hypothesis_id(title, rank),
        title=title,
        description=description,
        rank=rank,
        confidence=confidence,
        evidence_ids=evidence_ids,
        reasoning=reasoning,
        missing_evidence=missing_evidence,
        requires_human_review=True,
    )


def _generate_hypothesis_resource_saturation(
    patterns: dict, rank: int
) -> RootCauseHypothesis:
    """Generate hypothesis for resource saturation.

    Args:
        patterns: Evidence patterns
        rank: Hypothesis rank

    Returns:
        Root cause hypothesis
    """
    title = "Database resource saturation prevented new connections"

    evidence_ids = list(
        set(patterns["resource_saturation"] + patterns["pool_exhaustion"][:2])
    )

    confidence = 0.4 if patterns["resource_saturation"] else 0.2
    if len(patterns["resource_saturation"]) >= 2:
        confidence += 0.15

    confidence = min(confidence, 0.75)

    description = (
        "Database server resources (CPU, memory, or I/O) may have been saturated, "
        "preventing the server from accepting new connections or processing queries "
        "efficiently, leading to connection pool exhaustion."
    )

    reasoning = (
        f"Evidence shows {len(patterns['resource_saturation'])} indicator(s) of "
        "resource saturation. However, this hypothesis has lower confidence due to "
        "limited direct evidence of database server resource metrics."
    )

    missing_evidence = [
        "Database server CPU and memory utilization",
        "Disk I/O metrics",
        "Database server connection limit configuration",
        "Active process or query count on database server",
    ]

    return RootCauseHypothesis(
        hypothesis_id=_generate_hypothesis_id(title, rank),
        title=title,
        description=description,
        rank=rank,
        confidence=confidence,
        evidence_ids=evidence_ids,
        reasoning=reasoning,
        missing_evidence=missing_evidence,
        requires_human_review=True,
    )


class DemoDiagnosisAgent:
    """Deterministic demo diagnosis agent for offline operation.

    This agent performs evidence-grounded root cause diagnosis without
    making LLM calls or network requests. Generates multiple hypotheses
    ranked by confidence, distinguishing observations from causality.
    """

    def diagnose(
        self,
        incident: Incident,
        triage_result: TriageResult,
        evidence: List[EvidenceChunk],
    ) -> DiagnosisResult:
        """Perform root cause diagnosis based on incident, triage, and evidence.

        Args:
            incident: Incident object with metadata
            triage_result: Triage assessment result
            evidence: List of retrieved evidence chunks

        Returns:
            DiagnosisResult with ranked hypotheses

        Note:
            This is a deterministic implementation for demo mode.
            Distinguishes correlation from causation.
            Never recommends or executes remediation.
        """
        # Handle insufficient evidence
        if not evidence or len(evidence) < 3:
            return DiagnosisResult(
                incident_id=incident.incident_id,
                hypotheses=[],
                summary="Insufficient evidence for root cause diagnosis",
                limitations=[
                    "Fewer than 3 evidence chunks provided",
                    "Cannot establish causal relationships",
                ],
                insufficient_evidence=True,
                requires_human_review=True,
            )

        # Extract patterns from evidence
        patterns = _extract_evidence_patterns(evidence)
        sequences = _detect_causal_sequence(patterns, evidence)

        # Generate hypotheses
        hypotheses: List[RootCauseHypothesis] = []

        # Hypothesis 1: Connection pool exhaustion (if evidence exists)
        if patterns["pool_exhaustion"] and (
            patterns["http_5xx"] or patterns["service_failures"]
        ):
            hypotheses.append(
                _generate_hypothesis_pool_exhaustion(patterns, sequences, rank=1)
            )

        # Hypothesis 2: Long-running query (if evidence exists)
        if patterns["long_running_queries"] or (
            patterns["pool_exhaustion"] and len(evidence) >= 5
        ):
            hypotheses.append(
                _generate_hypothesis_long_running_query(
                    patterns, evidence, rank=len(hypotheses) + 1
                )
            )

        # Hypothesis 3: Resource saturation (if evidence suggests it)
        if patterns["resource_saturation"]:
            hypotheses.append(
                _generate_hypothesis_resource_saturation(
                    patterns, rank=len(hypotheses) + 1
                )
            )

        # Sort by confidence (highest first) and update ranks
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        for i, hyp in enumerate(hypotheses, 1):
            hyp.rank = i

        # Build summary
        if hypotheses:
            top_hypothesis = hypotheses[0]
            summary = (
                f"Generated {len(hypotheses)} root cause hypothesis(es). "
                f"Most likely: {top_hypothesis.title} "
                f"(confidence: {top_hypothesis.confidence:.2f}). "
                "All hypotheses require human review and validation."
            )
        else:
            summary = (
                "No plausible root cause hypotheses could be generated from "
                "the available evidence patterns."
            )

        # Document limitations
        limitations = [
            "Diagnosis based on correlation in evidence, not definitive causation",
            "Limited to patterns recognizable in log and runbook evidence",
            "Cannot verify hypotheses without additional investigation",
            "No remediation recommendations provided - human analysis required",
        ]

        if not patterns["long_running_queries"]:
            limitations.append(
                "Limited visibility into database query performance"
            )

        return DiagnosisResult(
            incident_id=incident.incident_id,
            hypotheses=hypotheses,
            summary=summary,
            limitations=limitations,
            insufficient_evidence=len(hypotheses) == 0,
            requires_human_review=True,
        )
