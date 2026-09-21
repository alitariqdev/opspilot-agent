"""Tests for log parsing functionality."""

from pathlib import Path

import pytest

from src.opspilot.tools.log_parser import (
    parse_log_file,
    parse_log_line,
)


def test_parse_valid_log_line():
    """Test parsing a correctly formatted log line."""
    line = "2024-03-15T14:20:16Z ERROR [order-service] Failed to create order"
    entry = parse_log_line(line, "test.log", 10)

    assert entry is not None
    assert entry.timestamp == "2024-03-15T14:20:16Z"
    assert entry.level == "ERROR"
    assert entry.service == "order-service"
    assert entry.message == "Failed to create order"
    assert entry.source_file == "test.log"
    assert entry.line_number == 10


def test_parse_log_line_with_complex_message():
    """Test parsing log line with special characters in message."""
    line = "2024-03-15T14:15:05Z INFO [reporting-worker] Executing query: SELECT * FROM orders WHERE id >= 100"
    entry = parse_log_line(line, "app.log", 5)

    assert entry is not None
    assert entry.service == "reporting-worker"
    assert "SELECT * FROM orders WHERE id >= 100" in entry.message


def test_parse_blank_line():
    """Test that blank lines return None."""
    entry = parse_log_line("", "test.log", 1)
    assert entry is None

    entry = parse_log_line("   ", "test.log", 2)
    assert entry is None


def test_parse_malformed_log_line():
    """Test that malformed lines return None without raising errors."""
    malformed_lines = [
        "This is not a valid log line",
        "2024-03-15 ERROR missing brackets",
        "[service] missing timestamp",
        "2024-03-15T14:20:16Z ONLY_THREE_PARTS [service]",
    ]

    for line in malformed_lines:
        entry = parse_log_line(line, "test.log", 1)
        assert entry is None


def test_parse_log_line_preserves_line_numbers():
    """Test that original line numbers are preserved."""
    entry1 = parse_log_line(
        "2024-03-15T14:20:16Z INFO [test] Message one",
        "test.log",
        42,
    )
    entry2 = parse_log_line(
        "2024-03-15T14:20:17Z INFO [test] Message two",
        "test.log",
        100,
    )

    assert entry1.line_number == 42
    assert entry2.line_number == 100


def test_parse_log_file(tmp_path: Path):
    """Test parsing an entire log file."""
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2024-03-15T14:15:03Z INFO [service-a] First message\n"
        "\n"
        "2024-03-15T14:15:04Z WARN [service-b] Second message\n"
        "Invalid line that should be skipped\n"
        "2024-03-15T14:15:05Z ERROR [service-c] Third message\n"
    )

    entries = parse_log_file(log_file)

    assert len(entries) == 3
    assert entries[0].service == "service-a"
    assert entries[0].line_number == 1
    assert entries[1].service == "service-b"
    assert entries[1].line_number == 3
    assert entries[2].service == "service-c"
    assert entries[2].line_number == 5


def test_parse_log_file_preserves_source_filename(tmp_path: Path):
    """Test that source filename is correctly recorded."""
    log_file = tmp_path / "application.log"
    log_file.write_text(
        "2024-03-15T14:15:03Z INFO [test] Message\n"
    )

    entries = parse_log_file(log_file)

    assert len(entries) == 1
    assert entries[0].source_file == "application.log"


def test_parse_empty_log_file(tmp_path: Path):
    """Test parsing an empty log file returns empty list."""
    log_file = tmp_path / "empty.log"
    log_file.write_text("")

    entries = parse_log_file(log_file)

    assert entries == []


def test_parse_log_file_with_different_log_levels(tmp_path: Path):
    """Test parsing various log levels."""
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2024-03-15T14:15:03Z DEBUG [service] Debug message\n"
        "2024-03-15T14:15:04Z INFO [service] Info message\n"
        "2024-03-15T14:15:05Z WARN [service] Warning message\n"
        "2024-03-15T14:15:06Z ERROR [service] Error message\n"
    )

    entries = parse_log_file(log_file)

    assert len(entries) == 4
    assert entries[0].level == "DEBUG"
    assert entries[1].level == "INFO"
    assert entries[2].level == "WARN"
    assert entries[3].level == "ERROR"
