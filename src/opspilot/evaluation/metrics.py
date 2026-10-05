"""Metric calculation for evaluation benchmark."""

from typing import List, Set

from src.opspilot.evaluation.models import (
    AggregateMetrics,
    BenchmarkCase,
    BenchmarkResult,
    DiagnosisMetrics,
    EvaluationMetrics,
    ServiceMetrics,
)
from src.opspilot.workflow import InvestigationState


def calculate_service_metrics(
    actual: Set[str], expected: Set[str]
) -> ServiceMetrics:
    """Calculate precision, recall, F1 for service identification.

    Args:
        actual: Actual services identified
        expected: Expected services

    Returns:
        ServiceMetrics with precision, recall, F1

    Metrics:
        precision = TP / (TP + FP) = correct / actual_count
        recall = TP / (TP + FN) = correct / expected_count
        f1 = 2 * (precision * recall) / (precision + recall)

    Note:
        Returns 0.0 for all metrics if both sets are empty.
        Returns 1.0 for precision if actual is empty and expected is empty.
    """
    if not actual and not expected:
        # Both empty: perfect match
        return ServiceMetrics(precision=1.0, recall=1.0, f1=1.0)

    if not actual:
        # Nothing predicted, but expected something
        return ServiceMetrics(precision=0.0, recall=0.0, f1=0.0)

    if not expected:
        # Predicted something, but expected nothing
        return ServiceMetrics(precision=0.0, recall=0.0, f1=0.0)

    # Calculate true positives (intersection)
    true_positives = len(actual & expected)

    # Precision: correct predictions / total predictions
    precision = true_positives / len(actual) if actual else 0.0

    # Recall: correct predictions / total expected
    recall = true_positives / len(expected) if expected else 0.0

    # F1: harmonic mean of precision and recall
    if precision + recall > 0:
        f1 = 2 * (precision * recall) / (precision + recall)
    else:
        f1 = 0.0

    return ServiceMetrics(precision=precision, recall=recall, f1=f1)


def calculate_diagnosis_metrics(
    actual: Set[str], expected: Set[str]
) -> DiagnosisMetrics:
    """Calculate precision and recall for diagnosis concepts.

    Args:
        actual: Actual diagnosis concepts (lowercase)
        expected: Expected diagnosis concepts (lowercase)

    Returns:
        DiagnosisMetrics with precision and recall

    Metrics:
        precision = relevant concepts / predicted concepts
        recall = relevant concepts / expected concepts

    Note:
        Returns 0.0 for both if both sets are empty.
        Returns 1.0 for precision if actual is empty and expected is empty.
    """
    if not actual and not expected:
        # Both empty: perfect match
        return DiagnosisMetrics(precision=1.0, recall=1.0)

    if not actual:
        # Nothing predicted, but expected something
        return DiagnosisMetrics(precision=0.0, recall=0.0)

    if not expected:
        # Predicted something, but expected nothing
        return DiagnosisMetrics(precision=0.0, recall=0.0)

    # Calculate relevant concepts (intersection)
    relevant = len(actual & expected)

    # Precision: relevant / predicted
    precision = relevant / len(actual) if actual else 0.0

    # Recall: relevant / expected
    recall = relevant / len(expected) if expected else 0.0

    return DiagnosisMetrics(precision=precision, recall=recall)


def extract_diagnosis_concepts(text: str) -> Set[str]:
    """Extract diagnosis concepts from text.

    Args:
        text: Hypothesis title, description, or reasoning text

    Returns:
        Set of lowercase concept keywords

    Note:
        Extracts words, removes common stop words, converts to lowercase.
    """
    # Simple keyword extraction: split on whitespace and punctuation
    import re

    words = re.findall(r"\b\w+\b", text.lower())

    # Remove common stop words
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "can",
        "this",
        "that",
        "these",
        "those",
    }

    return {w for w in words if w not in stop_words and len(w) > 2}


def validate_evidence_citations(
    cited_ids: List[str], available_ids: Set[str]
) -> float:
    """Validate evidence citations.

    Args:
        cited_ids: Evidence IDs cited in results
        available_ids: Available evidence IDs for this case

    Returns:
        Citation validity ratio (valid / total)

    Note:
        Returns 1.0 if no citations (vacuously true).
    """
    if not cited_ids:
        return 1.0

    valid_count = sum(1 for eid in cited_ids if eid in available_ids)
    return valid_count / len(cited_ids)


def calculate_rejected_claim_rate(
    rejected_concepts: Set[str], expected_rejected: Set[str]
) -> float:
    """Calculate rejected claim rate.

    Args:
        rejected_concepts: Concepts found in rejected hypotheses
        expected_rejected: Concepts that should be rejected

    Returns:
        Rejection rate (rejected / expected)

    Note:
        Returns 1.0 if no expected rejections.
    """
    if not expected_rejected:
        return 1.0

    rejected_count = len(rejected_concepts & expected_rejected)
    return rejected_count / len(expected_rejected)


def compute_metrics(
    case: BenchmarkCase,
    result: InvestigationState,
    available_evidence_ids: Set[str],
) -> EvaluationMetrics:
    """Compute evaluation metrics for a case.

    Args:
        case: Benchmark case with expected values
        result: Investigation result from workflow
        available_evidence_ids: Available evidence IDs for this case

    Returns:
        EvaluationMetrics with all computed metrics
    """
    # Check execution success
    execution_success = result["workflow_status"] == "complete" and not result.get(
        "errors"
    )

    # Extract actual values
    triage = result.get("triage_result")
    diagnosis = result.get("diagnosis_result")
    verification = result.get("verification_result")

    if not triage or not diagnosis or not verification:
        # Workflow didn't complete properly
        return EvaluationMetrics(
            severity_correct=False,
            service_metrics=ServiceMetrics(precision=0.0, recall=0.0, f1=0.0),
            diagnosis_metrics=DiagnosisMetrics(precision=0.0, recall=0.0),
            citation_validity=0.0,
            rejected_claim_rate=0.0,
            execution_success=False,
        )

    # Severity correctness
    actual_severity = triage.severity.value if hasattr(triage.severity, "value") else str(triage.severity)
    severity_correct = actual_severity == case.expected.severity

    # Service metrics
    actual_services = set(triage.affected_services)
    service_metrics = calculate_service_metrics(
        actual_services, case.expected.affected_services
    )

    # Diagnosis metrics: extract concepts from verified hypotheses
    actual_concepts = set()
    for hyp in verification.verified_hypotheses:
        actual_concepts.update(extract_diagnosis_concepts(hyp.title))
        actual_concepts.update(extract_diagnosis_concepts(hyp.description))

    diagnosis_metrics = calculate_diagnosis_metrics(
        actual_concepts, case.expected.diagnosis_concepts
    )

    # Citation validity: collect all cited evidence IDs
    cited_ids = []
    for event in triage.timeline:
        cited_ids.append(event.evidence_id)
    for hyp in verification.verified_hypotheses:
        cited_ids.extend(hyp.evidence_ids)

    citation_validity = validate_evidence_citations(cited_ids, available_evidence_ids)

    # Rejected claim rate: extract concepts from rejected hypotheses
    rejected_concepts = set()
    for hyp in diagnosis.hypotheses:
        if hyp.hypothesis_id in verification.rejected_hypothesis_ids:
            rejected_concepts.update(extract_diagnosis_concepts(hyp.title))
            rejected_concepts.update(extract_diagnosis_concepts(hyp.description))

    rejected_claim_rate = calculate_rejected_claim_rate(
        rejected_concepts, case.expected.rejected_claims
    )

    return EvaluationMetrics(
        severity_correct=severity_correct,
        service_metrics=service_metrics,
        diagnosis_metrics=diagnosis_metrics,
        citation_validity=citation_validity,
        rejected_claim_rate=rejected_claim_rate,
        execution_success=execution_success,
    )


def compute_aggregate_metrics(results: List[BenchmarkResult]) -> AggregateMetrics:
    """Compute aggregate metrics across all results.

    Args:
        results: List of benchmark results

    Returns:
        AggregateMetrics with averages across all cases
    """
    if not results:
        return AggregateMetrics(
            total_cases=0,
            successful_cases=0,
            severity_accuracy=0.0,
            avg_service_precision=0.0,
            avg_service_recall=0.0,
            avg_service_f1=0.0,
            avg_diagnosis_precision=0.0,
            avg_diagnosis_recall=0.0,
            avg_citation_validity=0.0,
            avg_rejected_claim_rate=0.0,
        )

    total_cases = len(results)
    successful_cases = sum(1 for r in results if r.metrics.execution_success)

    # Averages (including failed cases as 0.0)
    severity_accuracy = (
        sum(1 for r in results if r.metrics.severity_correct) / total_cases
    )
    avg_service_precision = (
        sum(r.metrics.service_metrics.precision for r in results) / total_cases
    )
    avg_service_recall = (
        sum(r.metrics.service_metrics.recall for r in results) / total_cases
    )
    avg_service_f1 = (
        sum(r.metrics.service_metrics.f1 for r in results) / total_cases
    )
    avg_diagnosis_precision = (
        sum(r.metrics.diagnosis_metrics.precision for r in results) / total_cases
    )
    avg_diagnosis_recall = (
        sum(r.metrics.diagnosis_metrics.recall for r in results) / total_cases
    )
    avg_citation_validity = (
        sum(r.metrics.citation_validity for r in results) / total_cases
    )
    avg_rejected_claim_rate = (
        sum(r.metrics.rejected_claim_rate for r in results) / total_cases
    )

    return AggregateMetrics(
        total_cases=total_cases,
        successful_cases=successful_cases,
        severity_accuracy=severity_accuracy,
        avg_service_precision=avg_service_precision,
        avg_service_recall=avg_service_recall,
        avg_service_f1=avg_service_f1,
        avg_diagnosis_precision=avg_diagnosis_precision,
        avg_diagnosis_recall=avg_diagnosis_recall,
        avg_citation_validity=avg_citation_validity,
        avg_rejected_claim_rate=avg_rejected_claim_rate,
    )
