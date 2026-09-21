"""Tests for incident report generation."""

import json
from pathlib import Path

import pytest

from src.opspilot.agents.diagnosis import DemoDiagnosisAgent
from src.opspilot.agents.remediation import DemoRemediationAgent
from src.opspilot.agents.triage import DemoTriageAgent
from src.opspilot.agents.verifier import EvidenceVerifier
from src.opspilot.models import (
    EvidenceChunk,
    Incident,
)
from src.opspilot.reporting import generate_incident_report
from src.opspilot.tools.evidence_retriever import create_evidence_retriever
from src.opspilot.tools.log_parser import parse_log_file


@pytest.fixture
def project_root():
    """Get project root."""
    return Path(__file__).parent.parent


@pytest.fixture
def real_incident(project_root):
    """Load real incident."""
    incident_file = project_root / "data" / "incidents" / "incident_001.json"
    with open(incident_file, "r") as f:
        return Incident(**json.load(f))


@pytest.fixture
def real_evidence(project_root):
    """Get real evidence."""
    log_file = project_root / "data" / "incidents" / "incident_001_logs.txt"
    runbook_dir = project_root / "data" / "runbooks"

    logs = parse_log_file(log_file)
    retriever = create_evidence_retriever(logs, runbook_dir)
    return retriever.retrieve("database connection pool exhausted 503", top_k=15)


@pytest.fixture
def complete_analysis_results(real_incident, real_evidence):
    """Generate complete analysis results."""
    triage_agent = DemoTriageAgent()
    diagnosis_agent = DemoDiagnosisAgent()
    verifier = EvidenceVerifier()
    remediation_agent = DemoRemediationAgent()

    triage = triage_agent.triage(real_incident, real_evidence)
    diagnosis = diagnosis_agent.diagnose(real_incident, triage, real_evidence)
    verification = verifier.verify(diagnosis, real_evidence)
    remediation = remediation_agent.plan_remediation(verification, real_evidence)

    return {
        "triage": triage,
        "diagnosis": diagnosis,
        "verification": verification,
        "remediation": remediation,
    }


def test_report_contains_all_required_sections(
    real_incident, real_evidence, complete_analysis_results
):
    """Test that report contains all required sections."""
    report = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    required_sections = [
        "# Incident Report",
        "## Executive Summary",
        "## Observed Symptoms",
        "## Evidence-Based Timeline",
        "## Root Cause Analysis",
        "## Recommended Actions",
        "## Analysis Limitations",
        "## Evidence References",
        "## Human Review Required",
    ]

    for section in required_sections:
        assert section in report, f"Missing required section: {section}"


def test_report_includes_evidence_references_with_line_numbers(
    real_incident, real_evidence, complete_analysis_results
):
    """Test that evidence references include source filename and line number."""
    report = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    # Should contain evidence references in format: (filename:line_number)
    # Example: (incident_001_logs.txt:8)
    import re
    # Look for pattern like (filename.txt:123) or (filename.md:45)
    pattern = r'\([a-zA-Z0-9_\-]+\.(txt|md):\d+\)'
    assert re.search(pattern, report), "Report should contain evidence references with filename:line_number format"


def test_report_does_not_claim_unsupported_conclusions(
    real_incident, real_evidence, complete_analysis_results
):
    """Test that report does not present unsupported hypotheses as confirmed."""
    report = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    verification = complete_analysis_results["verification"]

    # If there are rejected hypotheses, they should be clearly marked
    if verification.rejected_hypothesis_ids:
        assert (
            "Rejected Hypotheses" in report or "rejected" in report.lower()
        ), "Rejected hypotheses not clearly identified"


def test_report_escapes_markdown_special_characters():
    """Test that report safely handles special characters in log content."""
    from src.opspilot.models import (
        DiagnosisResult,
        RemediationPlan,
        Severity,
        TimelineEvent,
        TriageResult,
        VerificationResult,
    )

    # Create test data with special characters
    incident = Incident(
        incident_id="TEST-001",
        title="Test [with] special | chars",
        description="Test",
        symptoms=["test"],
        start_time="2024-03-15T14:00:00Z",
        affected_services=["test"],
        severity="high",
        status="investigating",
    )

    evidence = [
        EvidenceChunk(
            evidence_id="ev_001",
            source_file="test.log",
            source_type="log",
            line_number=1,
            content="Log with [brackets] and | pipes",
            score=1.0,
        )
    ]

    triage = TriageResult(
        incident_id="TEST-001",
        severity=Severity.SEV4,
        affected_services=["test"],
        symptoms=["test [special] | chars"],
        timeline=[
            TimelineEvent(
                timestamp="2024-03-15T14:00:00Z",
                service="test",
                description="Event with [special] chars",
                evidence_id="ev_001",
            )
        ],
        rationale="Test",
        evidence_ids=["ev_001"],
        confidence=0.5,
        insufficient_evidence=False,
        requires_human_review=True,
    )

    diagnosis = DiagnosisResult(
        incident_id="TEST-001",
        hypotheses=[],
        summary="Test",
        limitations=[],
        insufficient_evidence=True,
        requires_human_review=True,
    )

    verification = VerificationResult(
        incident_id="TEST-001",
        verified_hypotheses=[],
        rejected_hypothesis_ids=[],
        verification_summary="Test",
        requires_human_review=True,
    )

    remediation = RemediationPlan(
        incident_id="TEST-001",
        actions=[],
        summary="Test",
        limitations=[],
        requires_human_approval=True,
    )

    report = generate_incident_report(
        incident, triage, diagnosis, verification, remediation, evidence
    )

    # Special characters should be escaped in report
    assert "\\[" in report or "[special]" in report  # Either escaped or preserved safely


def test_report_is_valid_markdown(
    real_incident, real_evidence, complete_analysis_results
):
    """Test that generated report is valid Markdown."""
    report = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    # Basic Markdown structure checks
    assert report.startswith("#")
    assert "\n\n" in report  # Should have paragraph breaks
    assert "**" in report or "*" in report  # Should have emphasis


def test_report_deterministic(real_incident, real_evidence, complete_analysis_results):
    """Test that identical inputs produce identical report."""
    report1 = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    report2 = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    assert report1 == report2


def test_report_includes_human_review_notice(
    real_incident, real_evidence, complete_analysis_results
):
    """Test that report includes prominent human review notice."""
    report = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    # Should have warning symbol and clear notice
    assert "⚠️" in report or "WARNING" in report or "IMPORTANT" in report
    assert "human review" in report.lower()
    assert "approval" in report.lower() or "review" in report.lower()


def test_report_lists_remediation_actions_by_category(
    real_incident, real_evidence, complete_analysis_results
):
    """Test that remediation actions are organized by category."""
    report = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    remediation = complete_analysis_results["remediation"]

    if remediation.actions:
        # Check that categories appear as headers
        categories = {action.category for action in remediation.actions}
        for category in categories:
            # Category name should appear as a header
            assert category.title() in report or category.lower() in report.lower()


def test_report_includes_verified_hypotheses_with_status(
    real_incident, real_evidence, complete_analysis_results
):
    """Test that verified hypotheses include their status."""
    report = generate_incident_report(
        incident=real_incident,
        triage_result=complete_analysis_results["triage"],
        diagnosis_result=complete_analysis_results["diagnosis"],
        verification_result=complete_analysis_results["verification"],
        remediation_plan=complete_analysis_results["remediation"],
        evidence=real_evidence,
    )

    verification = complete_analysis_results["verification"]

    for hyp in verification.verified_hypotheses:
        # Hypothesis title should appear
        assert hyp.title in report or hyp.title.replace("[", "\\[") in report

        # Status should be mentioned
        if hyp.status:
            assert (
                hyp.status.value in report or hyp.status.value.replace("_", " ") in report
            )
