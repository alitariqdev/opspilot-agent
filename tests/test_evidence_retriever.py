"""Tests for evidence retrieval functionality."""

from pathlib import Path

import pytest

from src.opspilot.models import LogEntry
from src.opspilot.tools.evidence_retriever import (
    EvidenceRetriever,
    create_evidence_retriever,
)


@pytest.fixture
def sample_log_entries():
    """Create sample log entries for testing."""
    return [
        LogEntry(
            timestamp="2024-03-15T14:20:16Z",
            level="ERROR",
            service="order-service",
            message="database connection pool exhausted",
            source_file="incident_001_logs.txt",
            line_number=10,
        ),
        LogEntry(
            timestamp="2024-03-15T14:22:01Z",
            level="DEBUG",
            service="postgres",
            message="Connection pool: 20/20 connections active - pool exhausted",
            source_file="incident_001_logs.txt",
            line_number=15,
        ),
        LogEntry(
            timestamp="2024-03-15T14:25:33Z",
            level="DEBUG",
            service="postgres",
            message="Long-running query detected: query_id=9847 duration=622s",
            source_file="incident_001_logs.txt",
            line_number=25,
        ),
        LogEntry(
            timestamp="2024-03-15T14:15:03Z",
            level="INFO",
            service="api-gateway",
            message="Request processed successfully",
            source_file="incident_001_logs.txt",
            line_number=5,
        ),
    ]


def test_index_log_entries(sample_log_entries):
    """Test indexing log entries."""
    retriever = EvidenceRetriever()
    retriever.index_log_entries(sample_log_entries)

    assert len(retriever.corpus) == 4
    assert len(retriever.evidence_metadata) == 4
    assert all(
        meta["source_type"] == "log" for meta in retriever.evidence_metadata
    )


def test_retrieve_database_pool_evidence(sample_log_entries):
    """Test retrieving evidence about database connection pool issues."""
    retriever = EvidenceRetriever()
    retriever.index_log_entries(sample_log_entries)
    retriever.build_index()

    query = "database connection pool exhausted"
    results = retriever.retrieve(query, top_k=3)

    assert len(results) > 0
    # Results should include connection pool related logs
    pool_related = [
        r for r in results
        if "pool" in r.content.lower() or "connection" in r.content.lower()
    ]
    assert len(pool_related) > 0


def test_retrieve_returns_evidence_with_source_citations(sample_log_entries):
    """Test that retrieved evidence includes source file and line numbers."""
    retriever = EvidenceRetriever()
    retriever.index_log_entries(sample_log_entries)
    retriever.build_index()

    query = "connection pool"
    results = retriever.retrieve(query, top_k=5)

    assert len(results) > 0
    for result in results:
        assert result.source_file is not None
        assert result.line_number > 0
        assert result.evidence_id is not None
        assert result.source_type == "log"


def test_retrieve_returns_sorted_by_score(sample_log_entries):
    """Test that results are sorted by relevance score."""
    retriever = EvidenceRetriever()
    retriever.index_log_entries(sample_log_entries)
    retriever.build_index()

    query = "database pool"
    results = retriever.retrieve(query, top_k=4)

    assert len(results) > 0
    # Scores should be in descending order
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_with_empty_query(sample_log_entries):
    """Test that empty query returns empty list."""
    retriever = EvidenceRetriever()
    retriever.index_log_entries(sample_log_entries)
    retriever.build_index()

    results = retriever.retrieve("", top_k=10)
    assert results == []

    results = retriever.retrieve("   ", top_k=10)
    assert results == []


def test_retrieve_with_empty_corpus():
    """Test retrieval with empty corpus returns empty list."""
    retriever = EvidenceRetriever()
    retriever.build_index()

    results = retriever.retrieve("any query", top_k=10)
    assert results == []


def test_index_runbook(tmp_path: Path):
    """Test indexing a runbook file."""
    runbook_file = tmp_path / "test_runbook.md"
    runbook_file.write_text(
        "# Database Connection Pool Runbook\n"
        "\n"
        "## Symptoms\n"
        "\n"
        "Connection pool exhausted errors\n"
        "Application timeouts\n"
    )

    retriever = EvidenceRetriever()
    retriever.index_runbook(runbook_file)

    # Should index non-empty lines only
    assert len(retriever.corpus) > 0
    assert all(
        meta["source_type"] == "runbook"
        for meta in retriever.evidence_metadata
    )
    assert all(
        meta["source_file"] == "test_runbook.md"
        for meta in retriever.evidence_metadata
    )


def test_retrieve_from_runbook_content(tmp_path: Path):
    """Test retrieving evidence from runbook content."""
    runbook_file = tmp_path / "database.md"
    runbook_file.write_text(
        "Check connection pool utilization\n"
        "Identify long-running queries\n"
        "Review application logs for connection timeout\n"
    )

    retriever = EvidenceRetriever()
    retriever.index_runbook(runbook_file)
    retriever.build_index()

    query = "connection timeout"
    results = retriever.retrieve(query, top_k=3)

    assert len(results) > 0
    timeout_results = [r for r in results if "timeout" in r.content.lower()]
    assert len(timeout_results) > 0


def test_create_evidence_retriever_integration(sample_log_entries, tmp_path: Path):
    """Test the convenience function for creating a retriever."""
    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir()
    runbook_file = runbook_dir / "test.md"
    runbook_file.write_text("Database connection pool troubleshooting\n")

    retriever = create_evidence_retriever(sample_log_entries, runbook_dir)

    # Should have indexed both logs and runbooks
    assert len(retriever.corpus) > len(sample_log_entries)

    query = "database connection pool"
    results = retriever.retrieve(query, top_k=10)

    assert len(results) > 0
    # Should have both log and runbook evidence
    source_types = {r.source_type for r in results}
    assert "log" in source_types


def test_evidence_id_is_stable():
    """Test that evidence IDs are stable for same source."""
    entry = LogEntry(
        timestamp="2024-03-15T14:20:16Z",
        level="ERROR",
        service="test",
        message="test message",
        source_file="test.log",
        line_number=10,
    )

    retriever1 = EvidenceRetriever()
    retriever1.index_log_entries([entry])
    retriever1.build_index()
    results1 = retriever1.retrieve("test", top_k=1)

    retriever2 = EvidenceRetriever()
    retriever2.index_log_entries([entry])
    retriever2.build_index()
    results2 = retriever2.retrieve("test", top_k=1)

    assert len(results1) == 1
    assert len(results2) == 1
    assert results1[0].evidence_id == results2[0].evidence_id


def test_retrieve_respects_top_k_limit(sample_log_entries):
    """Test that retrieve returns at most top_k results."""
    retriever = EvidenceRetriever()
    retriever.index_log_entries(sample_log_entries)
    retriever.build_index()

    results = retriever.retrieve("service", top_k=2)
    assert len(results) <= 2

    results = retriever.retrieve("service", top_k=10)
    assert len(results) <= 10
    assert len(results) <= len(sample_log_entries)
