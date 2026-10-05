"""Tests for upload validation functionality."""

import pytest

from src.opspilot.upload_validator import (
    MAX_FILE_SIZE_BYTES,
    parse_uploaded_log_content,
    parse_uploaded_runbook_content,
    validate_evidence_availability,
    validate_file_content,
    validate_file_extension,
    validate_file_size,
    validate_uploaded_log_file,
    validate_uploaded_runbook_file,
    ALLOWED_LOG_EXTENSIONS,
    ALLOWED_RUNBOOK_EXTENSIONS,
)


class TestFileExtensionValidation:
    """Tests for file extension validation."""

    def test_valid_log_extensions(self):
        """Test that valid log extensions pass validation."""
        for ext in [".log", ".txt", ".LOG", ".TXT"]:
            filename = f"test{ext}"
            is_valid, error = validate_file_extension(filename, ALLOWED_LOG_EXTENSIONS)
            assert is_valid is True
            assert error is None

    def test_valid_runbook_extensions(self):
        """Test that valid runbook extensions pass validation."""
        for ext in [".md", ".txt", ".MD", ".TXT"]:
            filename = f"test{ext}"
            is_valid, error = validate_file_extension(filename, ALLOWED_RUNBOOK_EXTENSIONS)
            assert is_valid is True
            assert error is None

    def test_invalid_log_extension(self):
        """Test that invalid log extensions fail validation."""
        is_valid, error = validate_file_extension("test.csv", ALLOWED_LOG_EXTENSIONS)
        assert is_valid is False
        assert ".csv" in error
        assert "Invalid file type" in error

    def test_invalid_runbook_extension(self):
        """Test that invalid runbook extensions fail validation."""
        is_valid, error = validate_file_extension("test.pdf", ALLOWED_RUNBOOK_EXTENSIONS)
        assert is_valid is False
        assert ".pdf" in error

    def test_empty_filename(self):
        """Test that empty filename fails validation."""
        is_valid, error = validate_file_extension("", ALLOWED_LOG_EXTENSIONS)
        assert is_valid is False
        assert "empty" in error.lower()

    def test_no_extension(self):
        """Test that files without extension fail validation."""
        is_valid, error = validate_file_extension("testfile", ALLOWED_LOG_EXTENSIONS)
        assert is_valid is False


class TestFileSizeValidation:
    """Tests for file size validation."""

    def test_valid_size(self):
        """Test that valid file sizes pass validation."""
        is_valid, error = validate_file_size(1024)  # 1 KB
        assert is_valid is True
        assert error is None

        is_valid, error = validate_file_size(MAX_FILE_SIZE_BYTES)  # At limit
        assert is_valid is True
        assert error is None

    def test_empty_file(self):
        """Test that empty files fail validation."""
        is_valid, error = validate_file_size(0)
        assert is_valid is False
        assert "empty" in error.lower()

    def test_oversized_file(self):
        """Test that oversized files fail validation."""
        is_valid, error = validate_file_size(MAX_FILE_SIZE_BYTES + 1)
        assert is_valid is False
        assert "too large" in error.lower()
        assert "10" in error  # Should mention 10 MB limit


class TestFileContentValidation:
    """Tests for file content validation."""

    def test_valid_content(self):
        """Test that valid text content passes validation."""
        content = "2024-03-15T14:20:16Z INFO [service] Log message"
        is_valid, error = validate_file_content(content, "test.log")
        assert is_valid is True
        assert error is None

    def test_empty_content(self):
        """Test that empty content fails validation."""
        is_valid, error = validate_file_content("", "test.log")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_whitespace_only(self):
        """Test that whitespace-only content fails validation."""
        is_valid, error = validate_file_content("   \n\t\n  ", "test.log")
        assert is_valid is False
        assert "empty" in error.lower() or "whitespace" in error.lower()

    def test_binary_content(self):
        """Test that binary content fails validation."""
        content = "Some text\x00binary\x00data"
        is_valid, error = validate_file_content(content, "test.log")
        assert is_valid is False
        assert "binary" in error.lower() or "corrupted" in error.lower()


class TestUploadedLogFileValidation:
    """Tests for complete log file validation."""

    def test_valid_log_file(self):
        """Test validation of a valid log file."""
        content = b"2024-03-15T14:20:16Z INFO [service] Log message\n"
        is_valid, error = validate_uploaded_log_file("test.log", content, len(content))
        assert is_valid is True
        assert error is None

    def test_invalid_extension(self):
        """Test that invalid extension fails validation."""
        content = b"Valid content"
        is_valid, error = validate_uploaded_log_file("test.csv", content, len(content))
        assert is_valid is False
        assert "Invalid file type" in error

    def test_oversized_file(self):
        """Test that oversized file fails validation."""
        content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        is_valid, error = validate_uploaded_log_file("test.log", content, len(content))
        assert is_valid is False
        assert "too large" in error.lower()

    def test_non_utf8_content(self):
        """Test that non-UTF-8 content fails validation."""
        content = b"\x80\x81\x82"  # Invalid UTF-8
        is_valid, error = validate_uploaded_log_file("test.log", content, len(content))
        assert is_valid is False
        assert "UTF-8" in error


class TestUploadedRunbookFileValidation:
    """Tests for complete runbook file validation."""

    def test_valid_runbook_file(self):
        """Test validation of a valid runbook file."""
        content = b"# Runbook\n\nSome guidance\n"
        is_valid, error = validate_uploaded_runbook_file("test.md", content, len(content))
        assert is_valid is True
        assert error is None

    def test_invalid_extension(self):
        """Test that invalid extension fails validation."""
        content = b"Valid content"
        is_valid, error = validate_uploaded_runbook_file("test.pdf", content, len(content))
        assert is_valid is False
        assert "Invalid file type" in error


class TestParseUploadedLogContent:
    """Tests for parsing uploaded log content."""

    def test_parse_plain_text_logs(self):
        """Test parsing plain text log format."""
        content = (
            "2024-03-15T14:20:16Z INFO [service-a] First message\n"
            "2024-03-15T14:20:17Z ERROR [service-b] Second message\n"
            "\n"
            "2024-03-15T14:20:18Z WARN [service-c] Third message\n"
        )

        entries = parse_uploaded_log_content(content, "test.log")

        assert len(entries) == 3
        assert entries[0].service == "service-a"
        assert entries[0].source_file == "test.log"
        assert entries[0].line_number == 1
        assert entries[1].line_number == 2
        assert entries[2].line_number == 4

    def test_parse_docker_json_logs(self):
        """Test parsing Docker JSON log format."""
        content = (
            '{"log":"2024-03-15T14:20:16Z INFO [service] Message\\n","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}\n'
            '{"log":"2024-03-15T14:20:17Z ERROR [service] Error\\n","stream":"stderr","time":"2024-03-15T14:20:17.123456789Z"}\n'
        )

        entries = parse_uploaded_log_content(content, "container.docker.log")

        assert len(entries) == 2
        assert entries[0].service == "service"
        assert entries[0].log_source == "docker"
        assert entries[0].source_file == "container.docker.log"

    def test_parse_kubernetes_logs(self):
        """Test parsing Kubernetes log format."""
        content = (
            "2024-03-15T14:20:16.123456789Z stdout F 2024-03-15T14:20:16Z INFO [service] Message\n"
            "2024-03-15T14:20:17.123456789Z stderr F 2024-03-15T14:20:17Z ERROR [service] Error\n"
        )

        entries = parse_uploaded_log_content(content, "pod.k8s.log")

        assert len(entries) == 2
        assert entries[0].service == "service"
        assert entries[0].log_source == "kubernetes"
        assert entries[0].source_file == "pod.k8s.log"

    def test_parse_empty_log(self):
        """Test parsing empty log content."""
        entries = parse_uploaded_log_content("", "empty.log")
        assert len(entries) == 0

    def test_parse_malformed_logs(self):
        """Test parsing logs with some malformed lines."""
        content = (
            "2024-03-15T14:20:16Z INFO [service] Valid\n"
            "This is not a valid log line\n"
            "2024-03-15T14:20:17Z WARN [service] Also valid\n"
        )

        entries = parse_uploaded_log_content(content, "test.log")

        assert len(entries) == 2
        assert entries[0].level == "INFO"
        assert entries[1].level == "WARN"

    def test_preserves_filename_in_entries(self):
        """Test that original filename is preserved."""
        content = "2024-03-15T14:20:16Z INFO [service] Message\n"
        filename = "production-logs-2024.log"

        entries = parse_uploaded_log_content(content, filename)

        assert len(entries) == 1
        assert entries[0].source_file == filename


class TestParseUploadedRunbookContent:
    """Tests for parsing uploaded runbook content."""

    def test_parse_runbook_lines(self):
        """Test parsing runbook content."""
        content = (
            "# Database Connection Pool\n"
            "\n"
            "## Symptoms\n"
            "- Connection timeouts\n"
            "- Pool exhaustion\n"
        )

        lines = parse_uploaded_runbook_content(content, "runbook.md")

        assert len(lines) == 4  # Only non-empty lines
        assert lines[0] == (1, "# Database Connection Pool")
        assert lines[1] == (3, "## Symptoms")
        assert lines[2] == (4, "- Connection timeouts")
        assert lines[3] == (5, "- Pool exhaustion")

    def test_parse_empty_runbook(self):
        """Test parsing empty runbook."""
        lines = parse_uploaded_runbook_content("", "empty.md")
        assert len(lines) == 0

    def test_parse_whitespace_only(self):
        """Test parsing runbook with only whitespace."""
        content = "   \n\n\t\n  "
        lines = parse_uploaded_runbook_content(content, "whitespace.md")
        assert len(lines) == 0

    def test_preserves_line_numbers(self):
        """Test that line numbers are preserved correctly."""
        content = "Line 1\n\nLine 3\n\nLine 5\n"
        lines = parse_uploaded_runbook_content(content, "test.md")

        assert len(lines) == 3
        assert lines[0][0] == 1
        assert lines[1][0] == 3
        assert lines[2][0] == 5


class TestEvidenceAvailabilityValidation:
    """Tests for evidence availability validation."""

    def test_valid_with_logs_only(self):
        """Test validation passes with logs only."""
        is_valid, error = validate_evidence_availability(5, 0)
        assert is_valid is True
        assert error is None

    def test_valid_with_runbooks_only(self):
        """Test validation passes with runbooks only."""
        is_valid, error = validate_evidence_availability(0, 3)
        assert is_valid is True
        assert error is None

    def test_valid_with_both(self):
        """Test validation passes with both logs and runbooks."""
        is_valid, error = validate_evidence_availability(10, 5)
        assert is_valid is True
        assert error is None

    def test_invalid_with_no_evidence(self):
        """Test validation fails with no evidence."""
        is_valid, error = validate_evidence_availability(0, 0)
        assert is_valid is False
        assert "No evidence" in error
        assert "upload" in error.lower()


class TestSecurityAndSafety:
    """Tests for security and safe error handling."""

    def test_error_messages_safe(self):
        """Test that error messages don't expose internal paths."""
        # Test various invalid inputs
        _, error = validate_file_extension("test.exe", ALLOWED_LOG_EXTENSIONS)
        assert "/" not in error
        assert "\\" not in error

        _, error = validate_file_size(MAX_FILE_SIZE_BYTES + 1000)
        assert "path" not in error.lower()

    def test_binary_content_detected_safely(self):
        """Test binary content is detected without exposing data."""
        content = "Text\x00with\x00nulls"
        is_valid, error = validate_file_content(content, "test.log")
        assert is_valid is False
        assert "\x00" not in error  # Don't expose binary data

    def test_untrusted_content_not_executed(self):
        """Test that log content is never executed."""
        # Logs that could be dangerous if executed
        dangerous_content = (
            "2024-03-15T14:20:16Z INFO [service] rm -rf /\n"
            "2024-03-15T14:20:17Z WARN [service] __import__('os').system('ls')\n"
        )

        # Should parse safely without execution
        entries = parse_uploaded_log_content(dangerous_content, "test.log")

        # Content is preserved as text, never executed
        assert len(entries) == 2
        assert "rm -rf /" in entries[0].message
        assert "__import__" in entries[1].message
