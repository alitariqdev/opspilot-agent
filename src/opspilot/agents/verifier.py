"""Evidence verification agent for OpsPilot."""

from typing import Dict, List, Set, Tuple

from src.opspilot.models import (
    DiagnosisResult,
    EvidenceChunk,
    HypothesisStatus,
    RootCauseHypothesis,
    VerificationResult,
)


def _check_evidence_exists(
    hypothesis: RootCauseHypothesis, evidence_map: Dict[str, EvidenceChunk]
) -> Tuple[List[str], List[str]]:
    """Check which cited evidence IDs actually exist.

    Args:
        hypothesis: Hypothesis to check
        evidence_map: Map of evidence_id -> EvidenceChunk

    Returns:
        Tuple of (valid_ids, invalid_ids)
    """
    valid_ids = []
    invalid_ids = []

    for eid in hypothesis.evidence_ids:
        if eid in evidence_map:
            valid_ids.append(eid)
        else:
            invalid_ids.append(eid)

    return valid_ids, invalid_ids


def _verify_pool_exhaustion_claim(
    hypothesis: RootCauseHypothesis, evidence_map: Dict[str, EvidenceChunk]
) -> Tuple[HypothesisStatus, str, float]:
    """Verify claims about connection pool exhaustion.

    Args:
        hypothesis: Hypothesis to verify
        evidence_map: Available evidence

    Returns:
        Tuple of (status, explanation, confidence_adjustment)
    """
    # Look for pool exhaustion evidence
    pool_evidence_count = 0
    timeout_evidence_count = 0
    http_error_count = 0

    for eid in hypothesis.evidence_ids:
        if eid not in evidence_map:
            continue

        content_lower = evidence_map[eid].content.lower()

        if "pool exhausted" in content_lower or (
            "pool" in content_lower and "exhausted" in content_lower
        ):
            pool_evidence_count += 1
        if "timeout" in content_lower:
            timeout_evidence_count += 1
        if "503" in content_lower or "500" in content_lower:
            http_error_count += 1

    # Determine status
    if pool_evidence_count >= 2 and (timeout_evidence_count > 0 or http_error_count > 0):
        return (
            HypothesisStatus.SUPPORTED,
            f"Strong evidence: {pool_evidence_count} pool exhaustion indicators, "
            f"{timeout_evidence_count} timeouts, {http_error_count} HTTP errors",
            0.0,  # No adjustment needed
        )
    elif pool_evidence_count >= 1:
        return (
            HypothesisStatus.PARTIALLY_SUPPORTED,
            f"Partial evidence: {pool_evidence_count} pool exhaustion indicator(s), "
            f"but limited corroborating evidence of impact",
            -0.15,  # Reduce confidence
        )
    else:
        return (
            HypothesisStatus.UNSUPPORTED,
            "No evidence of connection pool exhaustion found in cited evidence",
            -0.5,  # Significant confidence reduction
        )


def _verify_long_running_query_claim(
    hypothesis: RootCauseHypothesis, evidence_map: Dict[str, EvidenceChunk]
) -> Tuple[HypothesisStatus, str, float]:
    """Verify claims about long-running queries.

    Args:
        hypothesis: Hypothesis to verify
        evidence_map: Available evidence

    Returns:
        Tuple of (status, explanation, confidence_adjustment)
    """
    query_evidence_count = 0
    pool_evidence_count = 0
    temporal_correlation = False

    for eid in hypothesis.evidence_ids:
        if eid not in evidence_map:
            continue

        content_lower = evidence_map[eid].content.lower()

        if "long-running query" in content_lower or (
            "query" in content_lower and "duration" in content_lower
        ):
            query_evidence_count += 1
        if "pool" in content_lower and "exhausted" in content_lower:
            pool_evidence_count += 1

    # Check for temporal correlation in hypothesis reasoning
    if "correlation" in hypothesis.reasoning.lower() or "preceded" in hypothesis.reasoning.lower():
        temporal_correlation = True

    if query_evidence_count >= 1 and pool_evidence_count >= 1:
        if temporal_correlation:
            return (
                HypothesisStatus.SUPPORTED,
                f"Evidence supports correlation: {query_evidence_count} query reference(s), "
                f"{pool_evidence_count} pool exhaustion indicator(s). "
                "Temporal sequence noted in reasoning.",
                0.0,
            )
        else:
            return (
                HypothesisStatus.PARTIALLY_SUPPORTED,
                f"Evidence present but causality not established: "
                f"{query_evidence_count} query reference(s), "
                f"{pool_evidence_count} pool exhaustion indicator(s)",
                -0.1,
            )
    elif query_evidence_count >= 1:
        return (
            HypothesisStatus.PARTIALLY_SUPPORTED,
            f"Query evidence found ({query_evidence_count} reference(s)) "
            "but connection to pool exhaustion not clearly established",
            -0.2,
        )
    else:
        return (
            HypothesisStatus.UNSUPPORTED,
            "No evidence of long-running queries found in cited evidence",
            -0.4,
        )


def _verify_resource_saturation_claim(
    hypothesis: RootCauseHypothesis, evidence_map: Dict[str, EvidenceChunk]
) -> Tuple[HypothesisStatus, str, float]:
    """Verify claims about resource saturation.

    Args:
        hypothesis: Hypothesis to verify
        evidence_map: Available evidence

    Returns:
        Tuple of (status, explanation, confidence_adjustment)
    """
    saturation_indicators = 0

    for eid in hypothesis.evidence_ids:
        if eid not in evidence_map:
            continue

        content_lower = evidence_map[eid].content.lower()

        if (
            "100%" in content_lower
            or "saturated" in content_lower
            or "maxed" in content_lower
        ):
            saturation_indicators += 1

    if saturation_indicators >= 2:
        return (
            HypothesisStatus.PARTIALLY_SUPPORTED,
            f"Some indicators present ({saturation_indicators}), "
            "but limited direct evidence of database server resource metrics",
            -0.1,
        )
    elif saturation_indicators >= 1:
        return (
            HypothesisStatus.PARTIALLY_SUPPORTED,
            f"Weak evidence: only {saturation_indicators} saturation indicator(s). "
            "Hypothesis remains speculative.",
            -0.25,
        )
    else:
        return (
            HypothesisStatus.UNSUPPORTED,
            "No evidence of resource saturation found in cited evidence",
            -0.3,
        )


def _verify_fabricated_hypothesis(
    hypothesis: RootCauseHypothesis, evidence_map: Dict[str, EvidenceChunk]
) -> Tuple[HypothesisStatus, str, float]:
    """Detect and reject fabricated hypotheses with no supporting evidence.

    Args:
        hypothesis: Hypothesis to verify
        evidence_map: Available evidence

    Returns:
        Tuple of (status, explanation, confidence_adjustment)
    """
    title_lower = hypothesis.title.lower()
    description_lower = hypothesis.description.lower()

    # Check for fabricated scenarios
    fabricated_keywords = [
        "dns",
        "security breach",
        "hardware failure",
        "network partition",
        "disk failure",
        "power outage",
        "ddos",
        "intrusion",
        "malware",
    ]

    for keyword in fabricated_keywords:
        if keyword in title_lower or keyword in description_lower:
            # Check if ANY evidence supports this claim
            has_supporting_evidence = False
            for eid in hypothesis.evidence_ids:
                if eid in evidence_map:
                    content_lower = evidence_map[eid].content.lower()
                    if keyword in content_lower:
                        has_supporting_evidence = True
                        break

            if not has_supporting_evidence:
                return (
                    HypothesisStatus.UNSUPPORTED,
                    f"Hypothesis references '{keyword}' but no evidence supports this claim. "
                    "Hypothesis appears fabricated.",
                    -0.8,  # Heavy penalty
                )

    return None  # Not a fabricated hypothesis


class EvidenceVerifier:
    """Deterministic evidence verification agent.

    Independently verifies diagnosis hypotheses against available evidence.
    Never invents new evidence or increases confidence scores.
    """

    def verify(
        self,
        diagnosis_result: DiagnosisResult,
        evidence: List[EvidenceChunk],
    ) -> VerificationResult:
        """Verify diagnosis hypotheses against available evidence.

        Args:
            diagnosis_result: Diagnosis result to verify
            evidence: Available evidence chunks

        Returns:
            VerificationResult with verified hypotheses

        Note:
            - Confirms all cited evidence IDs exist
            - Marks hypotheses as supported/partially_supported/unsupported
            - Removes invalid evidence citations
            - Never increases confidence scores
            - Never invents new evidence
        """
        # Build evidence map for fast lookup
        evidence_map = {e.evidence_id: e for e in evidence}

        verified_hypotheses: List[RootCauseHypothesis] = []
        rejected_ids: List[str] = []

        for hypothesis in diagnosis_result.hypotheses:
            # Check if evidence IDs are valid
            valid_ids, invalid_ids = _check_evidence_exists(
                hypothesis, evidence_map
            )

            if invalid_ids:
                # Remove invalid evidence IDs
                hypothesis.evidence_ids = valid_ids

            # If no valid evidence, reject hypothesis
            if not valid_ids:
                rejected_ids.append(hypothesis.hypothesis_id)
                continue

            # Check for fabricated hypotheses
            fabrication_check = _verify_fabricated_hypothesis(
                hypothesis, evidence_map
            )
            if fabrication_check:
                status, explanation, confidence_adj = fabrication_check
                hypothesis.status = status
                hypothesis.reasoning += f" [Verification: {explanation}]"
                hypothesis.confidence = max(
                    0.0, hypothesis.confidence + confidence_adj
                )
                if status == HypothesisStatus.UNSUPPORTED:
                    rejected_ids.append(hypothesis.hypothesis_id)
                    continue

            # Verify based on hypothesis content
            title_lower = hypothesis.title.lower()

            if "pool exhaustion" in title_lower or "connection pool" in title_lower:
                status, explanation, confidence_adj = (
                    _verify_pool_exhaustion_claim(hypothesis, evidence_map)
                )
            elif "long-running" in title_lower or "query" in title_lower:
                status, explanation, confidence_adj = (
                    _verify_long_running_query_claim(hypothesis, evidence_map)
                )
            elif "resource saturation" in title_lower or "resource" in title_lower:
                status, explanation, confidence_adj = (
                    _verify_resource_saturation_claim(hypothesis, evidence_map)
                )
            else:
                # Generic verification
                status = HypothesisStatus.PARTIALLY_SUPPORTED
                explanation = "Hypothesis type not specifically recognized; generic verification applied"
                confidence_adj = -0.1

            # Apply verification results
            hypothesis.status = status
            hypothesis.reasoning += f" [Verification: {explanation}]"

            # Adjust confidence (never increase, only decrease or maintain)
            new_confidence = hypothesis.confidence + confidence_adj
            hypothesis.confidence = max(0.0, min(hypothesis.confidence, new_confidence))

            # Add missing evidence note if evidence gaps were identified
            if invalid_ids:
                hypothesis.missing_evidence.append(
                    f"{len(invalid_ids)} cited evidence ID(s) could not be validated"
                )

            # Reject unsupported hypotheses
            if status == HypothesisStatus.UNSUPPORTED:
                rejected_ids.append(hypothesis.hypothesis_id)
            else:
                verified_hypotheses.append(hypothesis)

        # Build verification summary
        total_hypotheses = len(diagnosis_result.hypotheses)
        supported_count = sum(
            1
            for h in verified_hypotheses
            if h.status == HypothesisStatus.SUPPORTED
        )
        partial_count = sum(
            1
            for h in verified_hypotheses
            if h.status == HypothesisStatus.PARTIALLY_SUPPORTED
        )
        rejected_count = len(rejected_ids)

        if verified_hypotheses:
            summary = (
                f"Verified {total_hypotheses} hypothesis(es): "
                f"{supported_count} supported, {partial_count} partially supported, "
                f"{rejected_count} rejected. "
            )

            if supported_count > 0:
                top = verified_hypotheses[0]
                summary += (
                    f"Highest confidence: {top.title} "
                    f"({top.status.value}, confidence: {top.confidence:.2f}). "
                )

            summary += "All verified hypotheses require human review before action."
        else:
            summary = (
                f"All {total_hypotheses} hypothesis(es) were rejected during verification. "
                "No hypotheses have sufficient evidence support. "
                "Human expert review required."
            )

        return VerificationResult(
            incident_id=diagnosis_result.incident_id,
            verified_hypotheses=verified_hypotheses,
            rejected_hypothesis_ids=rejected_ids,
            verification_summary=summary,
            requires_human_review=True,
        )
