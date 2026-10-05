"""Upload validation and processing for user-uploaded evidence."""

from pathlib import Path
from typing import List, Optional, Tuple

from src.opspilot.models import LogEntry

# Maximum file size: 10 MB (safe limit for log and runbook files)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Allowed file extensions
ALLOWED_LOG_EXTENSIONS = {".log", ".txt"}
ALLOWED_RUNBOOK_EXTENSIONS = {".md", ".txt"}


class UploadValidationError(Exception):
    """Exception raised when uploaded file validation fails.

    This exception is safe to display to users as it never exposes
    internal paths, stack traces, or sensitive information.
    """

    pass


def validate_file_extension(
    filename: str, allowed_extensions: set[str]
) -> Tuple[bool, Optional[str]]:
    """Validate file extension.

    Args:
        filename: Name of the uploaded file
        allowed_extensions: Set of allowed extensions (e.g., {".log", ".txt"})

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, error_message)
    """
    if not filename:
        return False, "Filename cannot be empty"

    # Extract extension (case-insensitive)
    file_path = Path(filename)
    extension = file_path.suffix.lower()

    if extension not in allowed_extensions:
        allowed_str = ", ".join(sorted(allowed_extensions))
        return False, f"Invalid file type '{extension}'. Allowed types: {allowed_str}"

    return True, None


def validate_file_size(file_size: int) -> Tuple[bool, Optional[str]]:
    """Validate file size.

    Args:
        file_size: Size of file in bytes

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, error_message)
    """
    if file_size == 0:
        return False, "File is empty"

    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return (
            False,
            f"File too large ({actual_mb:.1f} MB). Maximum allowed: {max_mb:.0f} MB",
        )

    return True, None


def validate_file_content(content: str, filename: str) -> Tuple[bool, Optional[str]]:
    """Validate file content.

    Args:
        content: File content as string
        filename: Original filename for error messages

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, error_message)
    """
    if not content or content.strip() == "":
        return False, f"File '{filename}' is empty or contains only whitespace"

    # Check if content is readable (not binary or corrupted)
    # Since we're reading as text, the presence of null bytes indicates binary
    if "\x00" in content:
        return False, f"File '{filename}' appears to be binary or corrupted"

    return True, None


def validate_uploaded_log_file(
    filename: str, content: bytes, file_size: int
) -> Tuple[bool, Optional[str]]:
    """Validate an uploaded log file.

    Args:
        filename: Original filename
        content: File content as bytes
        file_size: File size in bytes

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, error_message)

    Note:
        This function performs all validation checks and returns
        the first error encountered.
    """
    # Validate extension
    is_valid, error = validate_file_extension(filename, ALLOWED_LOG_EXTENSIONS)
    if not is_valid:
        return False, error

    # Validate size
    is_valid, error = validate_file_size(file_size)
    if not is_valid:
        return False, error

    # Decode content
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        return False, f"File '{filename}' is not valid UTF-8 text"

    # Validate content
    is_valid, error = validate_file_content(content_str, filename)
    if not is_valid:
        return False, error

    return True, None


def validate_uploaded_runbook_file(
    filename: str, content: bytes, file_size: int
) -> Tuple[bool, Optional[str]]:
    """Validate an uploaded runbook file.

    Args:
        filename: Original filename
        content: File content as bytes
        file_size: File size in bytes

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, error_message)
    """
    # Validate extension
    is_valid, error = validate_file_extension(filename, ALLOWED_RUNBOOK_EXTENSIONS)
    if not is_valid:
        return False, error

    # Validate size
    is_valid, error = validate_file_size(file_size)
    if not is_valid:
        return False, error

    # Decode content
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        return False, f"File '{filename}' is not valid UTF-8 text"

    # Validate content
    is_valid, error = validate_file_content(content_str, filename)
    if not is_valid:
        return False, error

    return True, None


def parse_uploaded_log_content(
    content: str, original_filename: str
) -> List[LogEntry]:
    """Parse uploaded log file content into LogEntry objects.

    Args:
        content: Log file content as string
        original_filename: Original filename (preserved in LogEntry)

    Returns:
        List of parsed LogEntry objects

    Note:
        Uses existing log parsers to handle plain text and container logs.
        Preserves original filename and line numbers for citations.
        Returns empty list if no valid entries could be parsed.
    """
    from src.opspilot.tools.container_log_parser import (
        parse_docker_log_line,
        parse_kubernetes_log_line,
    )
    from src.opspilot.tools.log_parser import parse_log_line

    entries: List[LogEntry] = []
    lines = content.splitlines()

    # Detect format from first non-empty line
    format_type = "plain"  # Default
    for line in lines:
        if line.strip():
            # Check if Docker JSON format
            if line.strip().startswith("{"):
                format_type = "docker"
                break
            # Check if Kubernetes format (timestamp + stdout/stderr + F/P + message)
            parts = line.split(None, 3)
            if len(parts) >= 4 and parts[1] in ["stdout", "stderr"]:
                format_type = "kubernetes"
                break
            # Otherwise assume plain text
            break

    # Parse based on detected format
    for line_number, line in enumerate(lines, start=1):
        entry = None

        if format_type == "docker":
            entry = parse_docker_log_line(line, original_filename, line_number)
        elif format_type == "kubernetes":
            entry = parse_kubernetes_log_line(line, original_filename, line_number)
        else:
            entry = parse_log_line(line, original_filename, line_number)

        if entry is not None:
            entries.append(entry)

    return entries


def parse_uploaded_runbook_content(
    content: str, original_filename: str
) -> List[Tuple[int, str]]:
    """Parse uploaded runbook content into line-indexed chunks.

    Args:
        content: Runbook content as string
        original_filename: Original filename (for reference)

    Returns:
        List of tuples: (line_number, line_content)
        Only non-empty lines are included.

    Note:
        Line numbers are preserved for accurate evidence citations.
    """
    indexed_lines: List[Tuple[int, str]] = []
    lines = content.splitlines()

    for line_number, line in enumerate(lines, start=1):
        if line.strip():  # Only include non-empty lines
            indexed_lines.append((line_number, line.strip()))

    return indexed_lines


def validate_evidence_availability(
    log_files_count: int, runbook_files_count: int
) -> Tuple[bool, Optional[str]]:
    """Validate that at least some evidence is available.

    Args:
        log_files_count: Number of uploaded log files
        runbook_files_count: Number of uploaded runbook files

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, error_message)
    """
    if log_files_count == 0 and runbook_files_count == 0:
        return (
            False,
            "No evidence uploaded. Please upload at least one log file or runbook.",
        )

    return True, None
