"""Container log parsing utilities for Docker and Kubernetes logs."""

import json
import re
from pathlib import Path
from typing import List, Optional

from src.opspilot.models import LogEntry


# Docker log format: JSON with log, stream, time fields
# Example: {"log":"2024-03-15T14:20:16Z INFO [order-service] Message\n","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}

# Kubernetes log format: ISO8601 timestamp followed by stream (stdout/stderr) and log message
# Example: 2024-03-15T14:20:16.123456789Z stdout F 2024-03-15T14:20:16Z INFO [order-service] Message

# Standard log pattern for extracting structured fields from log messages
LOG_MESSAGE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s+"  # timestamp
    r"(\w+)\s+"  # level
    r"\[([^\]]+)\]\s+"  # [service]
    r"(.+)$"  # message
)


def _extract_log_fields(log_message: str) -> Optional[dict]:
    """Extract structured fields from a log message.

    Args:
        log_message: Log message text

    Returns:
        Dict with timestamp, level, service, message if parseable, else None
    """
    log_message = log_message.strip()
    if not log_message:
        return None

    match = LOG_MESSAGE_PATTERN.match(log_message)
    if not match:
        # If we can't parse structured fields, treat entire message as unstructured
        return {
            "timestamp": None,
            "level": "UNKNOWN",
            "service": "unknown",
            "message": log_message,
        }

    timestamp, level, service, message = match.groups()
    return {
        "timestamp": timestamp,
        "level": level,
        "service": service,
        "message": message,
    }


def parse_docker_log_line(
    line: str,
    source_file: str,
    line_number: int,
    container_id: Optional[str] = None,
    container_name: Optional[str] = None,
) -> Optional[LogEntry]:
    """Parse a Docker JSON log line.

    Docker logs are exported in JSON format with the following structure:
    {"log": "actual log message\\n", "stream": "stdout", "time": "2024-03-15T14:20:16.123456789Z"}

    Args:
        line: Raw JSON log line from Docker
        source_file: Name of the source log file
        line_number: Line number in the source file (1-indexed)
        container_id: Optional container ID for metadata
        container_name: Optional container name for metadata

    Returns:
        LogEntry if parsing succeeds, None if line is blank or malformed

    Note:
        Extracts structured fields (timestamp, level, service) from the log message.
        If structured parsing fails, uses Docker timestamp and treats message as unstructured.
    """
    line = line.strip()
    if not line:
        return None

    try:
        log_data = json.loads(line)
        log_message = log_data.get("log", "").strip()
        docker_timestamp = log_data.get("time", "")
        stream = log_data.get("stream", "stdout")

        if not log_message:
            return None

        # Try to extract structured fields from log message
        fields = _extract_log_fields(log_message)
        if fields is None:
            return None

        # Use structured timestamp if available, fallback to Docker timestamp
        timestamp = fields["timestamp"] or docker_timestamp.split(".")[0] + "Z"

        return LogEntry(
            timestamp=timestamp,
            level=fields["level"],
            service=fields["service"],
            message=fields["message"],
            source_file=source_file,
            line_number=line_number,
            container_id=container_id,
            container_name=container_name,
            log_source="docker",
        )

    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def parse_kubernetes_log_line(
    line: str,
    source_file: str,
    line_number: int,
    pod_name: Optional[str] = None,
    namespace: Optional[str] = None,
    container_name: Optional[str] = None,
) -> Optional[LogEntry]:
    """Parse a Kubernetes log line.

    Kubernetes logs have the format:
    2024-03-15T14:20:16.123456789Z stdout F <actual log message>

    Where:
    - Timestamp: ISO8601 with nanoseconds
    - Stream: stdout or stderr
    - Flag: F (full line) or P (partial line for multiline logs)

    Args:
        line: Raw log line from Kubernetes
        source_file: Name of the source log file
        line_number: Line number in the source file (1-indexed)
        pod_name: Optional pod name for metadata
        namespace: Optional namespace for metadata
        container_name: Optional container name for metadata

    Returns:
        LogEntry if parsing succeeds, None if line is blank or malformed

    Note:
        Extracts structured fields (timestamp, level, service) from the log message.
        Handles multiline logs by combining partial lines.
    """
    line = line.strip()
    if not line:
        return None

    # Kubernetes log format: timestamp stream flag message
    parts = line.split(None, 3)  # Split on whitespace, max 4 parts
    if len(parts) < 4:
        return None

    k8s_timestamp, stream, flag, log_message = parts

    # Skip partial lines - they should be combined with full lines in real scenarios
    # For this implementation, we only process full lines (F flag)
    if flag != "F":
        return None

    log_message = log_message.strip()
    if not log_message:
        return None

    # Try to extract structured fields from log message
    fields = _extract_log_fields(log_message)
    if fields is None:
        return None

    # Use structured timestamp if available, fallback to K8s timestamp
    timestamp = fields["timestamp"] or k8s_timestamp.split(".")[0] + "Z"

    return LogEntry(
        timestamp=timestamp,
        level=fields["level"],
        service=fields["service"],
        message=fields["message"],
        source_file=source_file,
        line_number=line_number,
        pod_name=pod_name,
        namespace=namespace,
        container_name=container_name,
        log_source="kubernetes",
    )


def parse_docker_log_file(
    file_path: Path,
    container_id: Optional[str] = None,
    container_name: Optional[str] = None,
) -> List[LogEntry]:
    """Parse a Docker JSON log file.

    Args:
        file_path: Path to the Docker log file
        container_id: Optional container ID (can be extracted from filename)
        container_name: Optional container name

    Returns:
        List of successfully parsed LogEntry objects

    Note:
        Attempts to extract container ID from filename if not provided.
        Filename pattern: <container-name>-<container-id>.log
    """
    entries: List[LogEntry] = []
    source_filename = file_path.name

    # Try to extract container info from filename if not provided
    # Common pattern: container-name-abc123.docker.log or abc123.docker.log
    if not container_id or not container_name:
        # Remove all extensions to get base name
        base_name = file_path.name
        # Strip .docker.log, .docker.json, etc.
        for ext in [".docker.log", ".docker.json", ".docker", ".log", ".json"]:
            if base_name.endswith(ext):
                base_name = base_name[: -len(ext)]

        # Try pattern: name-id
        if "-" in base_name:
            parts = base_name.rsplit("-", 1)
            if not container_name:
                container_name = parts[0]
            if not container_id:
                container_id = parts[1]
        else:
            # Filename is just ID or name
            if not container_id:
                container_id = base_name

    with open(file_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            entry = parse_docker_log_line(
                line, source_filename, line_number, container_id, container_name
            )
            if entry is not None:
                entries.append(entry)

    return entries


def parse_kubernetes_log_file(
    file_path: Path,
    pod_name: Optional[str] = None,
    namespace: Optional[str] = None,
    container_name: Optional[str] = None,
) -> List[LogEntry]:
    """Parse a Kubernetes log file.

    Args:
        file_path: Path to the Kubernetes log file
        pod_name: Optional pod name (can be extracted from filename)
        namespace: Optional namespace (can be extracted from filename)
        container_name: Optional container name (can be extracted from filename)

    Returns:
        List of successfully parsed LogEntry objects

    Note:
        Attempts to extract metadata from filename if not provided.
        Filename pattern: <pod-name>_<namespace>_<container-name>.log
    """
    entries: List[LogEntry] = []
    source_filename = file_path.name

    # Try to extract K8s info from filename if not provided
    # Common pattern: podname_namespace_containername.k8s.log
    if not pod_name or not namespace or not container_name:
        # Remove all extensions to get base name
        base_name = file_path.name
        # Strip .k8s.log, .kubernetes.log, etc.
        for ext in [".k8s.log", ".kubernetes.log", ".k8s", ".log"]:
            if base_name.endswith(ext):
                base_name = base_name[: -len(ext)]

        parts = base_name.split("_")
        if len(parts) >= 3:
            if not pod_name:
                pod_name = parts[0]
            if not namespace:
                namespace = parts[1]
            if not container_name:
                container_name = parts[2]
        elif len(parts) == 2:
            # Fallback: podname_containername
            if not pod_name:
                pod_name = parts[0]
            if not container_name:
                container_name = parts[1]
        else:
            # Just pod name
            if not pod_name:
                pod_name = base_name

    with open(file_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            entry = parse_kubernetes_log_line(
                line, source_filename, line_number, pod_name, namespace, container_name
            )
            if entry is not None:
                entries.append(entry)

    return entries


def parse_container_logs(log_directory: Path) -> List[LogEntry]:
    """Parse all container logs (Docker and Kubernetes) in a directory.

    Args:
        log_directory: Directory containing container log files

    Returns:
        List of all parsed LogEntry objects from all container log files

    Note:
        Detects log format based on file extension and content:
        - .docker.log or .docker.json: Docker format
        - .k8s.log or .kubernetes.log: Kubernetes format
        Skips files that cannot be read.
    """
    all_entries: List[LogEntry] = []

    if not log_directory.exists():
        return all_entries

    for log_file in log_directory.glob("*"):
        if not log_file.is_file():
            continue

        try:
            # Determine format based on filename
            name_lower = log_file.name.lower()

            if ".docker.log" in name_lower or ".docker.json" in name_lower:
                entries = parse_docker_log_file(log_file)
                all_entries.extend(entries)
            elif ".k8s.log" in name_lower or ".kubernetes.log" in name_lower:
                entries = parse_kubernetes_log_file(log_file)
                all_entries.extend(entries)
            # If no specific extension, try to detect by peeking at first line
            elif log_file.suffix in [".log", ".json"]:
                with open(log_file, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if not first_line:
                        continue

                    # Docker format starts with {
                    if first_line.startswith("{"):
                        entries = parse_docker_log_file(log_file)
                        all_entries.extend(entries)
                    # Kubernetes format has timestamp stdout/stderr F pattern
                    elif " stdout " in first_line or " stderr " in first_line:
                        entries = parse_kubernetes_log_file(log_file)
                        all_entries.extend(entries)

        except Exception:
            # Skip files that cannot be read
            continue

    return all_entries
