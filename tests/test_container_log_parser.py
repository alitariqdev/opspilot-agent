"""Tests for container log parsing functionality."""

from pathlib import Path

import pytest

from src.opspilot.tools.container_log_parser import (
    parse_docker_log_file,
    parse_docker_log_line,
    parse_kubernetes_log_file,
    parse_kubernetes_log_line,
    parse_container_logs,
)


class TestDockerLogParsing:
    """Tests for Docker JSON log parsing."""

    def test_parse_valid_docker_log_line(self):
        """Test parsing a valid Docker JSON log line."""
        line = '{"log":"2024-03-15T14:20:16Z ERROR [order-service] Failed to create order\\n","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}'
        entry = parse_docker_log_line(line, "test.log", 1, "abc123", "order-service")

        assert entry is not None
        assert entry.timestamp == "2024-03-15T14:20:16Z"
        assert entry.level == "ERROR"
        assert entry.service == "order-service"
        assert entry.message == "Failed to create order"
        assert entry.source_file == "test.log"
        assert entry.line_number == 1
        assert entry.container_id == "abc123"
        assert entry.container_name == "order-service"
        assert entry.log_source == "docker"

    def test_parse_docker_log_with_unstructured_message(self):
        """Test Docker log with unstructured message."""
        line = '{"log":"Application started successfully\\n","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}'
        entry = parse_docker_log_line(line, "test.log", 1)

        assert entry is not None
        assert entry.level == "UNKNOWN"
        assert entry.service == "unknown"
        assert entry.message == "Application started successfully"
        assert entry.log_source == "docker"

    def test_parse_docker_log_blank_line(self):
        """Test that blank lines return None."""
        assert parse_docker_log_line("", "test.log", 1) is None
        assert parse_docker_log_line("   ", "test.log", 1) is None

    def test_parse_docker_log_invalid_json(self):
        """Test that invalid JSON returns None."""
        line = "not valid json"
        assert parse_docker_log_line(line, "test.log", 1) is None

    def test_parse_docker_log_missing_fields(self):
        """Test Docker log with missing fields."""
        line = '{"stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}'
        assert parse_docker_log_line(line, "test.log", 1) is None

    def test_parse_docker_log_file(self, tmp_path: Path):
        """Test parsing a complete Docker log file."""
        log_file = tmp_path / "container.docker.log"
        log_file.write_text(
            '{"log":"2024-03-15T14:15:03Z INFO [service-a] First message\\n","stream":"stdout","time":"2024-03-15T14:15:03.123456789Z"}\n'
            '{"log":"\\n","stream":"stdout","time":"2024-03-15T14:15:04.123456789Z"}\n'
            '{"log":"2024-03-15T14:15:05Z WARN [service-b] Second message\\n","stream":"stderr","time":"2024-03-15T14:15:05.123456789Z"}\n'
        )

        entries = parse_docker_log_file(log_file)

        assert len(entries) == 2
        assert entries[0].service == "service-a"
        assert entries[0].level == "INFO"
        assert entries[0].line_number == 1
        assert entries[1].service == "service-b"
        assert entries[1].level == "WARN"
        assert entries[1].line_number == 3

    def test_parse_docker_log_file_extracts_container_info_from_filename(
        self, tmp_path: Path
    ):
        """Test extracting container info from filename."""
        log_file = tmp_path / "order-service-abc123.docker.log"
        log_file.write_text(
            '{"log":"2024-03-15T14:15:03Z INFO [order-service] Message\\n","stream":"stdout","time":"2024-03-15T14:15:03.123456789Z"}\n'
        )

        entries = parse_docker_log_file(log_file)

        assert len(entries) == 1
        assert entries[0].container_name == "order-service"
        assert entries[0].container_id == "abc123"


class TestKubernetesLogParsing:
    """Tests for Kubernetes log parsing."""

    def test_parse_valid_kubernetes_log_line(self):
        """Test parsing a valid Kubernetes log line."""
        line = "2024-03-15T14:20:16.123456789Z stdout F 2024-03-15T14:20:16Z ERROR [order-service] Failed to create order"
        entry = parse_kubernetes_log_line(
            line, "test.log", 1, "order-pod", "default", "order-service"
        )

        assert entry is not None
        assert entry.timestamp == "2024-03-15T14:20:16Z"
        assert entry.level == "ERROR"
        assert entry.service == "order-service"
        assert entry.message == "Failed to create order"
        assert entry.source_file == "test.log"
        assert entry.line_number == 1
        assert entry.pod_name == "order-pod"
        assert entry.namespace == "default"
        assert entry.container_name == "order-service"
        assert entry.log_source == "kubernetes"

    def test_parse_kubernetes_log_with_stderr(self):
        """Test Kubernetes log with stderr stream."""
        line = "2024-03-15T14:20:16.123456789Z stderr F 2024-03-15T14:20:16Z WARN [service] Warning message"
        entry = parse_kubernetes_log_line(line, "test.log", 1)

        assert entry is not None
        assert entry.level == "WARN"
        assert entry.message == "Warning message"

    def test_parse_kubernetes_log_partial_line(self):
        """Test that partial lines (P flag) are skipped."""
        line = "2024-03-15T14:20:16.123456789Z stdout P 2024-03-15T14:20:16Z ERROR [service] Partial"
        entry = parse_kubernetes_log_line(line, "test.log", 1)

        assert entry is None

    def test_parse_kubernetes_log_blank_line(self):
        """Test that blank lines return None."""
        assert parse_kubernetes_log_line("", "test.log", 1) is None
        assert parse_kubernetes_log_line("   ", "test.log", 1) is None

    def test_parse_kubernetes_log_malformed_line(self):
        """Test that malformed lines return None."""
        malformed_lines = [
            "not enough parts",
            "2024-03-15T14:20:16.123456789Z stdout",
            "timestamp stream flag",
        ]

        for line in malformed_lines:
            entry = parse_kubernetes_log_line(line, "test.log", 1)
            assert entry is None

    def test_parse_kubernetes_log_file(self, tmp_path: Path):
        """Test parsing a complete Kubernetes log file."""
        log_file = tmp_path / "pod.k8s.log"
        log_file.write_text(
            "2024-03-15T14:15:03.123456789Z stdout F 2024-03-15T14:15:03Z INFO [service-a] First message\n"
            "2024-03-15T14:15:04.123456789Z stdout P 2024-03-15T14:15:04Z INFO [service-a] Partial\n"
            "2024-03-15T14:15:05.123456789Z stderr F 2024-03-15T14:15:05Z ERROR [service-b] Error message\n"
        )

        entries = parse_kubernetes_log_file(log_file)

        assert len(entries) == 2
        assert entries[0].service == "service-a"
        assert entries[0].level == "INFO"
        assert entries[0].line_number == 1
        assert entries[1].service == "service-b"
        assert entries[1].level == "ERROR"
        assert entries[1].line_number == 3

    def test_parse_kubernetes_log_file_extracts_metadata_from_filename(
        self, tmp_path: Path
    ):
        """Test extracting pod/namespace/container from filename."""
        log_file = tmp_path / "order-pod_default_order-service.k8s.log"
        log_file.write_text(
            "2024-03-15T14:15:03.123456789Z stdout F 2024-03-15T14:15:03Z INFO [order-service] Message\n"
        )

        entries = parse_kubernetes_log_file(log_file)

        assert len(entries) == 1
        assert entries[0].pod_name == "order-pod"
        assert entries[0].namespace == "default"
        assert entries[0].container_name == "order-service"


class TestContainerLogDirectory:
    """Tests for parsing container log directories."""

    def test_parse_container_logs_directory(self, tmp_path: Path):
        """Test parsing a directory with mixed container logs."""
        # Create Docker log
        docker_log = tmp_path / "service-a.docker.log"
        docker_log.write_text(
            '{"log":"2024-03-15T14:15:03Z INFO [service-a] Docker message\\n","stream":"stdout","time":"2024-03-15T14:15:03.123456789Z"}\n'
        )

        # Create Kubernetes log
        k8s_log = tmp_path / "pod-b.k8s.log"
        k8s_log.write_text(
            "2024-03-15T14:15:04.123456789Z stdout F 2024-03-15T14:15:04Z WARN [service-b] K8s message\n"
        )

        entries = parse_container_logs(tmp_path)

        assert len(entries) == 2
        docker_entries = [e for e in entries if e.log_source == "docker"]
        k8s_entries = [e for e in entries if e.log_source == "kubernetes"]

        assert len(docker_entries) == 1
        assert len(k8s_entries) == 1
        assert docker_entries[0].service == "service-a"
        assert k8s_entries[0].service == "service-b"

    def test_parse_container_logs_auto_detect_format(self, tmp_path: Path):
        """Test auto-detection of log format from content."""
        # Docker log without .docker extension
        docker_log = tmp_path / "container1.log"
        docker_log.write_text(
            '{"log":"2024-03-15T14:15:03Z INFO [service-a] Message\\n","stream":"stdout","time":"2024-03-15T14:15:03.123456789Z"}\n'
        )

        # Kubernetes log without .k8s extension
        k8s_log = tmp_path / "container2.log"
        k8s_log.write_text(
            "2024-03-15T14:15:04.123456789Z stdout F 2024-03-15T14:15:04Z WARN [service-b] Message\n"
        )

        entries = parse_container_logs(tmp_path)

        assert len(entries) == 2
        sources = {e.log_source for e in entries}
        assert "docker" in sources
        assert "kubernetes" in sources

    def test_parse_container_logs_empty_directory(self, tmp_path: Path):
        """Test parsing an empty directory returns empty list."""
        entries = parse_container_logs(tmp_path)
        assert entries == []

    def test_parse_container_logs_nonexistent_directory(self):
        """Test parsing a nonexistent directory returns empty list."""
        entries = parse_container_logs(Path("/nonexistent/path"))
        assert entries == []

    def test_parse_container_logs_skips_invalid_files(self, tmp_path: Path):
        """Test that invalid files are skipped gracefully."""
        # Valid Docker log
        valid_log = tmp_path / "valid.docker.log"
        valid_log.write_text(
            '{"log":"2024-03-15T14:15:03Z INFO [service] Message\\n","stream":"stdout","time":"2024-03-15T14:15:03.123456789Z"}\n'
        )

        # Invalid Docker log
        invalid_log = tmp_path / "invalid.docker.log"
        invalid_log.write_text("not valid json\n")

        # Non-log file
        other_file = tmp_path / "readme.txt"
        other_file.write_text("This is not a log file\n")

        entries = parse_container_logs(tmp_path)

        assert len(entries) == 1
        assert entries[0].service == "service"


class TestContainerMetadataPreservation:
    """Tests for container metadata preservation."""

    def test_docker_log_preserves_all_metadata(self):
        """Test that Docker logs preserve all container metadata."""
        line = '{"log":"2024-03-15T14:20:16Z INFO [order-service] Message\\n","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}'
        entry = parse_docker_log_line(
            line, "order-service-abc123.log", 42, "abc123", "order-service"
        )

        assert entry is not None
        assert entry.source_file == "order-service-abc123.log"
        assert entry.line_number == 42
        assert entry.container_id == "abc123"
        assert entry.container_name == "order-service"
        assert entry.log_source == "docker"
        assert entry.pod_name is None
        assert entry.namespace is None

    def test_kubernetes_log_preserves_all_metadata(self):
        """Test that Kubernetes logs preserve all metadata."""
        line = "2024-03-15T14:20:16.123456789Z stdout F 2024-03-15T14:20:16Z INFO [order-service] Message"
        entry = parse_kubernetes_log_line(
            line, "order-pod-123.log", 42, "order-pod-123", "production", "app"
        )

        assert entry is not None
        assert entry.source_file == "order-pod-123.log"
        assert entry.line_number == 42
        assert entry.pod_name == "order-pod-123"
        assert entry.namespace == "production"
        assert entry.container_name == "app"
        assert entry.log_source == "kubernetes"
        assert entry.container_id is None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_docker_log_with_special_characters_in_message(self):
        """Test Docker log with special characters."""
        line = '{"log":"2024-03-15T14:20:16Z ERROR [service] Failed: \\"connection timeout\\" at 10.0.0.1\\n","stream":"stderr","time":"2024-03-15T14:20:16.123456789Z"}'
        entry = parse_docker_log_line(line, "test.log", 1)

        assert entry is not None
        assert 'Failed: "connection timeout"' in entry.message

    def test_kubernetes_log_with_multiline_indicator(self):
        """Test Kubernetes log with multiline indicators."""
        line = "2024-03-15T14:20:16.123456789Z stdout F 2024-03-15T14:20:16Z ERROR [service] Exception occurred"
        entry = parse_kubernetes_log_line(line, "test.log", 1)

        assert entry is not None
        assert entry.message == "Exception occurred"

    def test_docker_log_empty_log_field(self):
        """Test Docker log with empty log field."""
        line = '{"log":"","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}'
        entry = parse_docker_log_line(line, "test.log", 1)

        assert entry is None

    def test_kubernetes_log_empty_message(self):
        """Test Kubernetes log with empty message."""
        line = "2024-03-15T14:20:16.123456789Z stdout F    "
        entry = parse_kubernetes_log_line(line, "test.log", 1)

        assert entry is None
