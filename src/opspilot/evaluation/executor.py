"""Benchmark execution logic."""

import json
from pathlib import Path
from typing import List, Set

from src.opspilot.config import OpsPilotConfig, get_config
from src.opspilot.evaluation.metrics import compute_aggregate_metrics, compute_metrics
from src.opspilot.evaluation.models import (
    BenchmarkCase,
    BenchmarkReport,
    BenchmarkResult,
)
from src.opspilot.models import Incident
from src.opspilot.tools.evidence_retriever import EvidenceRetriever
from src.opspilot.tools.log_parser import parse_log_file
from src.opspilot.workflow import run_investigation


def load_benchmark_cases(cases_file: Path) -> List[BenchmarkCase]:
    """Load benchmark cases from JSON file.

    Args:
        cases_file: Path to benchmark_cases.json

    Returns:
        List of BenchmarkCase objects

    Note:
        Cases are sorted by case_id for deterministic ordering.
    """
    with open(cases_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = [BenchmarkCase(**case_data) for case_data in data]

    # Sort by case_id for deterministic ordering
    cases.sort(key=lambda c: c.case_id)

    return cases


def load_incident(incident_id: str, data_dir: Path) -> Incident:
    """Load incident metadata from JSON file.

    Args:
        incident_id: Incident ID (e.g., "INC-2024-001")
        data_dir: Path to data directory

    Returns:
        Incident object
    """
    # Try multiple filename patterns
    incident_dir = data_dir / "incidents"
    possible_names = [
        f"{incident_id}.json",
        f"{incident_id.lower()}.json",
        f"{incident_id.replace('-', '_').lower()}.json",
    ]

    # Extract numeric part and try incident_NNN.json
    import re

    match = re.search(r"(\d+)$", incident_id)
    if match:
        num = match.group(1)
        possible_names.append(f"incident_{num}.json")

    for name in possible_names:
        incident_file = incident_dir / name
        if incident_file.exists():
            with open(incident_file, "r", encoding="utf-8") as f:
                incident_data = json.load(f)
            return Incident(**incident_data)

    raise FileNotFoundError(
        f"Incident file not found for {incident_id}. Tried: {possible_names}"
    )


def create_evidence_retriever_for_case(
    case: BenchmarkCase, data_dir: Path
) -> tuple[EvidenceRetriever, Set[str]]:
    """Create evidence retriever for a benchmark case.

    Args:
        case: Benchmark case
        data_dir: Path to data directory

    Returns:
        Tuple of (evidence_retriever, available_evidence_ids)
    """
    # Parse log file
    log_path = data_dir / "incidents" / case.log_file
    logs = parse_log_file(log_path)

    # Find runbooks
    runbook_dir = data_dir / case.runbook_dir

    # Create retriever
    from src.opspilot.tools.evidence_retriever import create_evidence_retriever

    retriever = create_evidence_retriever(logs, runbook_dir)

    # Collect available evidence IDs
    available_ids = {meta["source_file"] + ":" + str(meta["line_number"])
                     for meta in retriever.evidence_metadata}

    # Also generate proper evidence IDs using the same hash function
    from src.opspilot.tools.evidence_retriever import _generate_evidence_id

    available_ids = {
        _generate_evidence_id(meta["source_file"], meta["line_number"])
        for meta in retriever.evidence_metadata
    }

    return retriever, available_ids


def execute_case(
    case: BenchmarkCase,
    data_dir: Path,
    mode: str = "demo",
    config: OpsPilotConfig = None,
) -> BenchmarkResult:
    """Execute a single benchmark case.

    Args:
        case: Benchmark case to execute
        data_dir: Path to data directory
        mode: Execution mode (demo or live)
        config: Optional configuration (uses default if not provided)

    Returns:
        BenchmarkResult with metrics and actual values
    """
    try:
        # Load incident
        incident = load_incident(case.incident_id, data_dir)

        # Create evidence retriever
        retriever, available_ids = create_evidence_retriever_for_case(case, data_dir)

        # Build query from incident
        query_parts = [incident.title]
        query_parts.extend(incident.symptoms[:3])
        investigation_query = " ".join(query_parts)

        # Run investigation
        result = run_investigation(
            incident=incident,
            investigation_query=investigation_query,
            config=config,
            evidence_retriever=retriever,
        )

        # Compute metrics
        metrics = compute_metrics(case, result, available_ids)

        # Extract actual values for reporting
        triage = result.get("triage_result")
        diagnosis = result.get("diagnosis_result")
        verification = result.get("verification_result")

        actual_severity = (
            triage.severity.value if triage and hasattr(triage.severity, "value")
            else str(triage.severity) if triage
            else "UNKNOWN"
        )

        actual_services = list(triage.affected_services) if triage else []

        # Extract actual diagnosis concepts
        from src.opspilot.evaluation.metrics import extract_diagnosis_concepts

        actual_concepts_set = set()
        if verification:
            for hyp in verification.verified_hypotheses:
                actual_concepts_set.update(extract_diagnosis_concepts(hyp.title))
                actual_concepts_set.update(extract_diagnosis_concepts(hyp.description))

        actual_concepts = sorted(list(actual_concepts_set))

        # Collect cited evidence IDs
        cited_ids = []
        if triage:
            for event in triage.timeline:
                cited_ids.append(event.evidence_id)
        if verification:
            for hyp in verification.verified_hypotheses:
                cited_ids.extend(hyp.evidence_ids)

        # Extract rejected concepts
        rejected_concepts_set = set()
        if diagnosis and verification:
            for hyp in diagnosis.hypotheses:
                if hyp.hypothesis_id in verification.rejected_hypothesis_ids:
                    rejected_concepts_set.update(extract_diagnosis_concepts(hyp.title))
                    rejected_concepts_set.update(
                        extract_diagnosis_concepts(hyp.description)
                    )

        rejected_concepts = sorted(list(rejected_concepts_set))

        errors = result.get("errors", [])

        return BenchmarkResult(
            case_id=case.case_id,
            mode=mode,
            metrics=metrics,
            actual_severity=actual_severity,
            actual_services=actual_services,
            actual_concepts=actual_concepts,
            cited_evidence_ids=cited_ids,
            rejected_concepts=rejected_concepts,
            errors=errors,
        )

    except Exception as e:
        # Handle execution errors safely
        from src.opspilot.evaluation.models import (
            DiagnosisMetrics,
            EvaluationMetrics,
            ServiceMetrics,
        )

        error_type = type(e).__name__
        safe_error = f"Execution failed: {error_type}"

        return BenchmarkResult(
            case_id=case.case_id,
            mode=mode,
            metrics=EvaluationMetrics(
                severity_correct=False,
                service_metrics=ServiceMetrics(precision=0.0, recall=0.0, f1=0.0),
                diagnosis_metrics=DiagnosisMetrics(precision=0.0, recall=0.0),
                citation_validity=0.0,
                rejected_claim_rate=0.0,
                execution_success=False,
            ),
            actual_severity="ERROR",
            actual_services=[],
            actual_concepts=[],
            cited_evidence_ids=[],
            rejected_concepts=[],
            errors=[safe_error],
        )


def run_benchmark(
    cases_file: Path,
    data_dir: Path,
    mode: str = "demo",
    config: OpsPilotConfig = None,
) -> BenchmarkReport:
    """Run complete benchmark evaluation.

    Args:
        cases_file: Path to benchmark_cases.json
        data_dir: Path to data directory
        mode: Execution mode (demo or live)
        config: Optional configuration

    Returns:
        BenchmarkReport with aggregate and per-case results
    """
    # Load cases
    cases = load_benchmark_cases(cases_file)

    # Execute each case
    results = []
    for case in cases:
        result = execute_case(case, data_dir, mode, config)
        results.append(result)

    # Compute aggregate metrics
    aggregate = compute_aggregate_metrics(results)

    return BenchmarkReport(
        mode=mode,
        aggregate=aggregate,
        results=results,
    )
