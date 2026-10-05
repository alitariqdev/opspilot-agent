"""Log parsing utilities for OpsPilot."""

import re
from pathlib import Path
from typing import List, Optional

from src.opspilot.models import LogEntry


# Expected log format: YYYY-MM-DDTHH:MM:SSZ LEVEL [service] message
LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s+"  # timestamp
    r"(\w+)\s+"  # level
    r"\[([^\]]+)\]\s+"  # [service]
    r"(.+)$"  # message
)


def parse_log_line(
    line: str, source_file: str, line_number: int
) -> Optional[LogEntry]:
    """Parse a single log line into a LogEntry.

    Args:
        line: Raw log line text
        source_file: Name of the source log file
        line_number: Line number in the source file (1-indexed)

    Returns:
        LogEntry if parsing succeeds, None if line is blank or malformed

    Note:
        Does not invent missing values - returns None for unparseable lines
    """
    line = line.strip()

    if not line:
        return None

    match = LOG_PATTERN.match(line)
    if not match:
        return None

    timestamp, level, service, message = match.groups()

    return LogEntry(
        timestamp=timestamp,
        level=level,
        service=service,
        message=message,
        source_file=source_file,
        line_number=line_number,
    )


def parse_log_file(file_path: Path) -> List[LogEntry]:
    """Parse a log file into a list of LogEntry objects.

    Args:
        file_path: Path to the log file

    Returns:
        List of successfully parsed LogEntry objects

    Note:
        Skips blank and malformed lines without raising errors.
        Preserves original line numbers from the source file.
    """
    entries: List[LogEntry] = []
    source_filename = file_path.name

    with open(file_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            entry = parse_log_line(line, source_filename, line_number)
            if entry is not None:
                entries.append(entry)

    return entries


def parse_log_files(log_directory: Path, include_container_logs: bool = True) -> List[LogEntry]:
    """Parse all log files in a directory.

    Args:
        log_directory: Directory containing log files
        include_container_logs: Whether to parse Docker/Kubernetes logs (default: True)

    Returns:
        List of all parsed LogEntry objects from all files

    Note:
        Processes plain text logs (.txt, .log) and container logs (.docker.log, .k8s.log).
        Skips files that cannot be read.
    """
    all_entries: List[LogEntry] = []

    if not log_directory.exists():
        return all_entries

    # Import container parser if needed
    if include_container_logs:
        try:
            from src.opspilot.tools.container_log_parser import parse_container_logs
            container_entries = parse_container_logs(log_directory)
            all_entries.extend(container_entries)
        except ImportError:
            pass

    # Parse plain text logs
    for log_file in log_directory.glob("*"):
        # Skip container logs (already processed) and non-log files
        name_lower = log_file.name.lower()
        if ".docker." in name_lower or ".k8s." in name_lower or ".kubernetes." in name_lower:
            continue

        if log_file.suffix in [".txt", ".log"] and log_file.is_file():
            try:
                entries = parse_log_file(log_file)
                all_entries.extend(entries)
            except Exception:
                # Skip files that cannot be read
                continue

    return all_entries
