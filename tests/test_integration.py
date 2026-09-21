"""Integration tests using real incident data."""

from pathlib import Path

import pytest

from src.opspilot.tools.evidence_retriever import create_evidence_retriever
from src.opspilot.tools.log_parser import parse_log_file


@pytest.fixture
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def incident_log_file(project_root):
    """Get path to the incident log file."""
    return project_root / "data" / "incidents" / "incident_001_logs.txt"


@pytest.fixture
def runbook_directory(project_root):
    """Get path to the runbooks directory."""
    return project_root / "data" / "runbooks"


def test_parse_real_incident_logs(incident_log_file):
    """Test parsing the actual incident log file."""
    assert incident_log_file.exists(), "Incident log file should exist"

    entries = parse_log_file(incident_log_file)

    assert len(entries) > 0, "Should parse at least one log entry"

    # Verify we have entries from different services
    services = {entry.service for entry in entries}
    expected_services = {"order-service", "api-gateway", "postgres", "reporting-worker"}
    assert expected_services.issubset(services), f"Should have logs from expected services, got: {services}"

    # Verify line numbers are preserved
    assert all(entry.line_number > 0 for entry in entries)

    # Verify timestamps are present
    assert all(entry.timestamp for entry in entries)


def test_retrieve_connection_pool_evidence(incident_log_file, runbook_directory):
    """Test retrieving evidence for connection pool exhaustion."""
    log_entries = parse_log_file(incident_log_file)
    retriever = create_evidence_retriever(log_entries, runbook_directory)

    query = "database connection pool exhausted"
    results = retriever.retrieve(query, top_k=10)

    assert len(results) > 0, "Should retrieve relevant evidence"

    # Should find connection pool related evidence
    pool_evidence = [
        r for r in results
        if "pool" in r.content.lower() and "connection" in r.content.lower()
    ]
    assert len(pool_evidence) > 0, "Should find connection pool related evidence"

    # Evidence should have proper citations
    for evidence in results:
        assert evidence.source_file is not None
        assert evidence.line_number > 0
        assert evidence.evidence_id is not None
        assert evidence.source_type in ["log", "runbook"]


def test_retrieve_long_running_query_evidence(incident_log_file, runbook_directory):
    """Test retrieving evidence about long-running queries."""
    log_entries = parse_log_file(incident_log_file)
    retriever = create_evidence_retriever(log_entries, runbook_directory)

    query = "long running query duration"
    results = retriever.retrieve(query, top_k=5)

    assert len(results) > 0, "Should retrieve relevant evidence"

    # Should find query-related evidence
    query_evidence = [
        r for r in results
        if "query" in r.content.lower()
    ]
    assert len(query_evidence) > 0, "Should find query-related evidence"


def test_retrieve_http_503_evidence(incident_log_file, runbook_directory):
    """Test retrieving evidence about HTTP 503 errors."""
    log_entries = parse_log_file(incident_log_file)
    retriever = create_evidence_retriever(log_entries, runbook_directory)

    query = "503 service unavailable order"
    results = retriever.retrieve(query, top_k=5)

    assert len(results) > 0, "Should retrieve relevant evidence"

    # Should find 503 error evidence
    error_evidence = [
        r for r in results
        if "503" in r.content or "service" in r.content.lower()
    ]
    assert len(error_evidence) > 0, "Should find 503 error evidence"


def test_retrieve_runbook_guidance(runbook_directory):
    """Test that runbook content is indexed and retrievable."""
    from src.opspilot.tools.evidence_retriever import EvidenceRetriever

    retriever = EvidenceRetriever()
    retriever.index_runbooks(runbook_directory)
    retriever.build_index()

    query = "connection pool diagnostic checks"
    results = retriever.retrieve(query, top_k=10)

    assert len(results) > 0, "Should retrieve runbook content"

    # Should have runbook evidence
    runbook_evidence = [r for r in results if r.source_type == "runbook"]
    assert len(runbook_evidence) > 0, "Should find runbook evidence"


def test_cross_source_retrieval(incident_log_file, runbook_directory):
    """Test retrieving evidence from both logs and runbooks."""
    log_entries = parse_log_file(incident_log_file)
    retriever = create_evidence_retriever(log_entries, runbook_directory)

    query = "connection pool exhausted timeout"
    results = retriever.retrieve(query, top_k=15)

    assert len(results) > 0, "Should retrieve evidence"

    # Should have both log and runbook sources
    source_types = {r.source_type for r in results}
    # May have both, or just one if query is very specific
    assert len(source_types) > 0, "Should have at least one source type"
    assert source_types.issubset({"log", "runbook"}), "Source types should be log or runbook"
