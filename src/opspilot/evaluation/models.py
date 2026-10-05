"""Models for evaluation benchmark."""

from typing import List, Optional, Set

from pydantic import BaseModel, Field


class ExpectedValues(BaseModel):
    """Expected values for a benchmark case.

    Attributes:
        severity: Expected severity level (SEV1, SEV2, SEV3, SEV4)
        affected_services: Expected affected service names
        diagnosis_concepts: Expected diagnosis keywords or concepts
        must_cite_evidence: Evidence IDs that must be cited
        rejected_claims: Concepts/keywords that should be rejected
    """

    severity: str = Field(description="Expected severity (SEV1-SEV4)")
    affected_services: Set[str] = Field(
        default_factory=set, description="Expected affected services"
    )
    diagnosis_concepts: Set[str] = Field(
        default_factory=set,
        description="Expected diagnosis keywords (lowercase)",
    )
    must_cite_evidence: List[str] = Field(
        default_factory=list,
        description="Evidence IDs that must be cited (optional)",
    )
    rejected_claims: Set[str] = Field(
        default_factory=set,
        description="Concepts that should be rejected (lowercase)",
    )


class BenchmarkCase(BaseModel):
    """A single benchmark case for evaluation.

    Attributes:
        case_id: Unique identifier for this case
        name: Human-readable case name
        description: Description of what this case tests
        incident_id: Incident ID to investigate
        log_file: Path to log file (relative to data/incidents)
        runbook_dir: Path to runbooks (relative to data)
        expected: Expected values for evaluation
    """

    case_id: str = Field(description="Unique case identifier")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="What this case tests")
    incident_id: str = Field(description="Incident ID to investigate")
    log_file: str = Field(description="Log file path (relative to data/incidents)")
    runbook_dir: str = Field(description="Runbook directory (relative to data)")
    expected: ExpectedValues = Field(description="Expected values")


class ServiceMetrics(BaseModel):
    """Precision, recall, F1 for service identification.

    Metrics:
        precision: TP / (TP + FP) - accuracy of predicted services
        recall: TP / (TP + FN) - coverage of actual services
        f1: 2 * (precision * recall) / (precision + recall)
    """

    precision: float = Field(description="Precision (0.0 to 1.0)", ge=0.0, le=1.0)
    recall: float = Field(description="Recall (0.0 to 1.0)", ge=0.0, le=1.0)
    f1: float = Field(description="F1 score (0.0 to 1.0)", ge=0.0, le=1.0)


class DiagnosisMetrics(BaseModel):
    """Precision and recall for diagnosis concepts.

    Metrics:
        precision: Relevant concepts / predicted concepts
        recall: Relevant concepts / expected concepts
    """

    precision: float = Field(description="Precision (0.0 to 1.0)", ge=0.0, le=1.0)
    recall: float = Field(description="Recall (0.0 to 1.0)", ge=0.0, le=1.0)


class EvaluationMetrics(BaseModel):
    """Evaluation metrics for a single case.

    Attributes:
        severity_correct: True if severity matches expected
        service_metrics: Precision, recall, F1 for services
        diagnosis_metrics: Precision, recall for diagnosis concepts
        citation_validity: Ratio of valid evidence citations
        rejected_claim_rate: Ratio of expected-rejected claims actually rejected
        execution_success: True if workflow completed without errors
    """

    severity_correct: bool = Field(description="Severity matches expected")
    service_metrics: ServiceMetrics = Field(description="Service identification metrics")
    diagnosis_metrics: DiagnosisMetrics = Field(description="Diagnosis metrics")
    citation_validity: float = Field(
        description="Valid citations ratio (0.0 to 1.0)", ge=0.0, le=1.0
    )
    rejected_claim_rate: float = Field(
        description="Rejected claim ratio (0.0 to 1.0)", ge=0.0, le=1.0
    )
    execution_success: bool = Field(description="Workflow completed successfully")


class BenchmarkResult(BaseModel):
    """Result for a single benchmark case.

    Attributes:
        case_id: Benchmark case identifier
        mode: Evaluation mode (demo or live)
        metrics: Computed evaluation metrics
        actual_severity: Actual severity from triage
        actual_services: Actual services identified
        actual_concepts: Actual diagnosis concepts found
        cited_evidence_ids: Evidence IDs cited in results
        rejected_concepts: Concepts found in rejected hypotheses
        errors: List of errors encountered (empty if successful)
    """

    case_id: str = Field(description="Benchmark case ID")
    mode: str = Field(description="Evaluation mode (demo or live)")
    metrics: EvaluationMetrics = Field(description="Evaluation metrics")
    actual_severity: str = Field(description="Actual severity from triage")
    actual_services: List[str] = Field(
        default_factory=list, description="Actual services identified"
    )
    actual_concepts: List[str] = Field(
        default_factory=list, description="Actual diagnosis concepts"
    )
    cited_evidence_ids: List[str] = Field(
        default_factory=list, description="Evidence IDs cited"
    )
    rejected_concepts: List[str] = Field(
        default_factory=list, description="Concepts in rejected hypotheses"
    )
    errors: List[str] = Field(default_factory=list, description="Errors encountered")


class AggregateMetrics(BaseModel):
    """Aggregate metrics across all benchmark cases.

    Attributes:
        total_cases: Total number of cases evaluated
        successful_cases: Number of cases that executed successfully
        severity_accuracy: Ratio of correct severity predictions
        avg_service_precision: Average service precision
        avg_service_recall: Average service recall
        avg_service_f1: Average service F1
        avg_diagnosis_precision: Average diagnosis precision
        avg_diagnosis_recall: Average diagnosis recall
        avg_citation_validity: Average citation validity
        avg_rejected_claim_rate: Average rejected claim rate
    """

    total_cases: int = Field(description="Total cases evaluated")
    successful_cases: int = Field(description="Cases executed successfully")
    severity_accuracy: float = Field(
        description="Severity accuracy (0.0 to 1.0)", ge=0.0, le=1.0
    )
    avg_service_precision: float = Field(
        description="Average service precision", ge=0.0, le=1.0
    )
    avg_service_recall: float = Field(
        description="Average service recall", ge=0.0, le=1.0
    )
    avg_service_f1: float = Field(description="Average service F1", ge=0.0, le=1.0)
    avg_diagnosis_precision: float = Field(
        description="Average diagnosis precision", ge=0.0, le=1.0
    )
    avg_diagnosis_recall: float = Field(
        description="Average diagnosis recall", ge=0.0, le=1.0
    )
    avg_citation_validity: float = Field(
        description="Average citation validity", ge=0.0, le=1.0
    )
    avg_rejected_claim_rate: float = Field(
        description="Average rejected claim rate", ge=0.0, le=1.0
    )


class BenchmarkReport(BaseModel):
    """Complete benchmark report.

    Attributes:
        mode: Evaluation mode (demo or live)
        aggregate: Aggregate metrics across all cases
        results: Per-case results
    """

    mode: str = Field(description="Evaluation mode")
    aggregate: AggregateMetrics = Field(description="Aggregate metrics")
    results: List[BenchmarkResult] = Field(
        default_factory=list, description="Per-case results"
    )
