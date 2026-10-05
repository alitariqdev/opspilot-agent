"""Tests for upload handler functionality."""

from io import BytesIO

import pytest

from src.opspilot.upload_handler import (
    create_evidence_retriever_from_uploads,
    process_uploaded_logs,
    process_uploaded_runbooks,
    UploadedEvidence,
)


class FakeUploadedFile:
    """Fake Streamlit UploadedFile for testing."""

    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def read(self):
        return self._content


class TestUploadedEvidenceContainer:
    """Tests for UploadedEvidence container class."""

    def test_empty_evidence(self):
        """Test empty evidence container."""
        evidence = UploadedEvidence()

        assert len(evidence.log_entries) == 0
        assert len(evidence.runbook_lines) == 0
        assert not evidence.has_evidence()
        assert "No evidence" in evidence.get_summary()

    def test_add_log_entries(self):
        """Test adding log entries."""
        from src.opspilot.models import LogEntry

        evidence = UploadedEvidence()

        entries = [
            LogEntry(
                timestamp="2024-03-15T14:20:16Z",
                level="INFO",
                service="service-a",
                message="Message",
                source_file="test.log",
                line_number=1,
            )
        ]

        evidence.add_log_file("test.log", entries)

        assert len(evidence.log_entries) == 1
        assert "test.log" in evidence.log_filenames
        assert evidence.has_evidence()

    def test_add_runbook_lines(self):
        """Test adding runbook lines."""
        evidence = UploadedEvidence()

        lines = [(1, "Line 1"), (2, "Line 2")]
        evidence.add_runbook_file("runbook.md", lines)

        assert len(evidence.runbook_lines) == 2
        assert "runbook.md" in evidence.runbook_filenames
        assert evidence.has_evidence()

    def test_summary_with_logs_only(self):
        """Test summary with logs only."""
        from src.opspilot.models import LogEntry

        evidence = UploadedEvidence()
        entries = [
            LogEntry(
                timestamp="2024-03-15T14:20:16Z",
                level="INFO",
                service="service",
                message="Message",
                source_file="test.log",
                line_number=1,
            )
        ]
        evidence.add_log_file("test.log", entries)

        summary = evidence.get_summary()
        assert "1 log entries" in summary
        assert "1 file(s)" in summary

    def test_summary_with_runbooks_only(self):
        """Test summary with runbooks only."""
        evidence = UploadedEvidence()
        lines = [(1, "Line 1"), (2, "Line 2")]
        evidence.add_runbook_file("runbook.md", lines)

        summary = evidence.get_summary()
        assert "2 runbook lines" in summary
        assert "1 file(s)" in summary


class TestProcessUploadedLogs:
    """Tests for processing uploaded log files."""

    def test_process_single_valid_log(self):
        """Test processing a single valid log file."""
        content = b"2024-03-15T14:20:16Z INFO [service] Message\n"
        fake_file = FakeUploadedFile("test.log", content)

        entries, filenames, errors = process_uploaded_logs([fake_file])

        assert len(entries) == 1
        assert entries[0].service == "service"
        assert len(filenames) == 1
        assert "test.log" in filenames
        assert len(errors) == 0

    def test_process_multiple_valid_logs(self):
        """Test processing multiple valid log files."""
        file1 = FakeUploadedFile(
            "log1.log", b"2024-03-15T14:20:16Z INFO [service-a] Message\n"
        )
        file2 = FakeUploadedFile(
            "log2.txt", b"2024-03-15T14:20:17Z WARN [service-b] Warning\n"
        )

        entries, filenames, errors = process_uploaded_logs([file1, file2])

        assert len(entries) == 2
        assert len(filenames) == 2
        assert "log1.log" in filenames
        assert "log2.txt" in filenames
        assert len(errors) == 0

    def test_process_invalid_extension(self):
        """Test processing file with invalid extension."""
        fake_file = FakeUploadedFile("test.csv", b"some,csv,data")

        entries, filenames, errors = process_uploaded_logs([fake_file])

        assert len(entries) == 0
        assert len(filenames) == 0
        assert len(errors) == 1
        assert "Invalid file type" in errors[0]

    def test_process_empty_log(self):
        """Test processing empty log file."""
        fake_file = FakeUploadedFile("empty.log", b"")

        entries, filenames, errors = process_uploaded_logs([fake_file])

        assert len(entries) == 0
        assert len(errors) == 1
        assert "empty" in errors[0].lower()

    def test_process_oversized_log(self):
        """Test processing oversized log file."""
        from src.opspilot.upload_validator import MAX_FILE_SIZE_BYTES

        content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        fake_file = FakeUploadedFile("huge.log", content)

        entries, filenames, errors = process_uploaded_logs([fake_file])

        assert len(entries) == 0
        assert len(errors) == 1
        assert "too large" in errors[0].lower()

    def test_process_mixed_valid_and_invalid(self):
        """Test processing mix of valid and invalid files."""
        valid_file = FakeUploadedFile(
            "valid.log", b"2024-03-15T14:20:16Z INFO [service] Message\n"
        )
        invalid_file = FakeUploadedFile("invalid.csv", b"csv,data")

        entries, filenames, errors = process_uploaded_logs([valid_file, invalid_file])

        assert len(entries) == 1
        assert len(filenames) == 1
        assert "valid.log" in filenames
        assert len(errors) == 1
        assert "Invalid file type" in errors[0] or ".csv" in errors[0]

    def test_preserves_original_filenames(self):
        """Test that original filenames are preserved in entries."""
        fake_file = FakeUploadedFile(
            "production-2024-03-15.log",
            b"2024-03-15T14:20:16Z INFO [service] Message\n",
        )

        entries, filenames, errors = process_uploaded_logs([fake_file])

        assert len(entries) == 1
        assert entries[0].source_file == "production-2024-03-15.log"

    def test_safe_error_handling(self):
        """Test that errors are handled safely without exposing internals."""
        # Test with non-UTF-8 content
        fake_file = FakeUploadedFile("test.log", b"\x80\x81\x82")

        entries, filenames, errors = process_uploaded_logs([fake_file])

        assert len(errors) == 1
        # Error message should be safe, not expose internal details
        assert "\x80" not in errors[0]
        assert "UTF-8" in errors[0]


class TestProcessUploadedRunbooks:
    """Tests for processing uploaded runbook files."""

    def test_process_single_valid_runbook(self):
        """Test processing a single valid runbook file."""
        content = b"# Runbook\n\n## Section\nContent line\n"
        fake_file = FakeUploadedFile("runbook.md", content)

        lines, filenames, errors = process_uploaded_runbooks([fake_file])

        assert len(lines) == 3  # Non-empty lines
        assert len(filenames) == 1
        assert "runbook.md" in filenames
        assert len(errors) == 0

    def test_process_multiple_runbooks(self):
        """Test processing multiple runbook files."""
        file1 = FakeUploadedFile("runbook1.md", b"# Runbook 1\nContent\n")
        file2 = FakeUploadedFile("runbook2.txt", b"Runbook 2\nMore content\n")

        lines, filenames, errors = process_uploaded_runbooks([file1, file2])

        assert len(lines) == 4  # Total non-empty lines
        assert len(filenames) == 2
        assert len(errors) == 0

    def test_process_invalid_runbook_extension(self):
        """Test processing runbook with invalid extension."""
        fake_file = FakeUploadedFile("doc.pdf", b"PDF content")

        lines, filenames, errors = process_uploaded_runbooks([fake_file])

        assert len(lines) == 0
        assert len(errors) == 1
        assert "Invalid file type" in errors[0]

    def test_preserves_filename_and_line_numbers(self):
        """Test that filename and line numbers are preserved."""
        content = b"Line 1\n\nLine 3\n"
        fake_file = FakeUploadedFile("test.md", content)

        lines, filenames, errors = process_uploaded_runbooks([fake_file])

        assert len(lines) == 2
        assert lines[0] == ("test.md", 1, "Line 1")
        assert lines[1] == ("test.md", 3, "Line 3")


class TestCreateEvidenceRetrieverFromUploads:
    """Tests for creating evidence retriever from uploads."""

    def test_create_retriever_with_logs_only(self):
        """Test creating retriever with log entries only."""
        from src.opspilot.models import LogEntry

        entries = [
            LogEntry(
                timestamp="2024-03-15T14:20:16Z",
                level="ERROR",
                service="service",
                message="Database connection failed",
                source_file="test.log",
                line_number=1,
            )
        ]

        retriever = create_evidence_retriever_from_uploads(entries, [])

        # Should be able to retrieve evidence
        results = retriever.retrieve("database connection", top_k=5)
        assert len(results) > 0
        assert "database" in results[0].content.lower()

    def test_create_retriever_with_runbooks_only(self):
        """Test creating retriever with runbook lines only."""
        lines = [
            ("runbook.md", 1, "Database Connection Pool Troubleshooting"),
            ("runbook.md", 2, "Check pool size configuration"),
        ]

        retriever = create_evidence_retriever_from_uploads([], lines)

        results = retriever.retrieve("connection pool", top_k=5)
        assert len(results) > 0
        assert "pool" in results[0].content.lower()

    def test_create_retriever_with_both(self):
        """Test creating retriever with both logs and runbooks."""
        from src.opspilot.models import LogEntry

        log_entries = [
            LogEntry(
                timestamp="2024-03-15T14:20:16Z",
                level="ERROR",
                service="service",
                message="Connection pool exhausted",
                source_file="app.log",
                line_number=5,
            )
        ]

        runbook_lines = [
            ("runbook.md", 10, "Increase connection pool size"),
        ]

        retriever = create_evidence_retriever_from_uploads(log_entries, runbook_lines)

        results = retriever.retrieve("connection pool", top_k=10)

        assert len(results) >= 2
        sources = {r.source_file for r in results}
        assert "app.log" in sources
        assert "runbook.md" in sources

    def test_evidence_preserves_citations(self):
        """Test that evidence chunks preserve file and line info."""
        from src.opspilot.models import LogEntry

        entries = [
            LogEntry(
                timestamp="2024-03-15T14:20:16Z",
                level="ERROR",
                service="order-service",
                message="Connection timeout",
                source_file="production-2024-03-15.log",
                line_number=42,
            )
        ]

        retriever = create_evidence_retriever_from_uploads(entries, [])
        results = retriever.retrieve("connection timeout", top_k=1)

        assert len(results) == 1
        assert results[0].source_file == "production-2024-03-15.log"
        assert results[0].line_number == 42

    def test_retriever_is_functional(self):
        """Test that retriever can be used for investigation."""
        from src.opspilot.models import LogEntry

        entries = [
            LogEntry(
                timestamp="2024-03-15T14:20:16Z",
                level="ERROR",
                service="api",
                message="Request timeout",
                source_file="api.log",
                line_number=1,
            ),
            LogEntry(
                timestamp="2024-03-15T14:20:17Z",
                level="ERROR",
                service="db",
                message="Connection failed",
                source_file="db.log",
                line_number=1,
            ),
            LogEntry(
                timestamp="2024-03-15T14:20:18Z",
                level="INFO",
                service="cache",
                message="Cache hit",
                source_file="cache.log",
                line_number=1,
            ),
        ]

        retriever = create_evidence_retriever_from_uploads(entries, [])

        # Should retrieve most relevant results
        results = retriever.retrieve("timeout connection", top_k=2)

        assert len(results) == 2
        # Timeout and connection errors should rank higher than cache hit
        messages = [r.content.lower() for r in results]
        assert any("timeout" in m for m in messages)
        assert any("connection" in m or "failed" in m for m in messages)


class TestIntegrationWithWorkflow:
    """Tests for integration with incident investigation workflow."""

    def test_uploaded_evidence_in_workflow(self):
        """Test that uploaded evidence can be used in workflow."""
        from src.opspilot.models import Incident, LogEntry

        # Create incident
        incident = Incident(
            incident_id="UPLOAD-TEST-001",
            title="Test Incident",
            description="Testing uploaded evidence",
            symptoms=["Service unavailable"],
            start_time="2024-03-15T14:00:00Z",
            affected_services=["test-service"],
            severity="high",
            status="investigating",
        )

        # Create uploaded evidence
        log_entries = [
            LogEntry(
                timestamp="2024-03-15T14:20:16Z",
                level="ERROR",
                service="test-service",
                message="Database connection pool exhausted",
                source_file="uploaded.log",
                line_number=1,
            )
        ]

        runbook_lines = [
            ("uploaded-runbook.md", 1, "Check connection pool configuration"),
        ]

        # Create retriever
        retriever = create_evidence_retriever_from_uploads(log_entries, runbook_lines)

        # Verify retriever works
        results = retriever.retrieve("database connection pool", top_k=5)
        assert len(results) > 0
        assert any("pool" in r.content.lower() for r in results)
