"""Upload handler for processing user-uploaded evidence files."""

from typing import List, Tuple

from src.opspilot.models import LogEntry
from src.opspilot.tools.evidence_retriever import EvidenceRetriever
from src.opspilot.upload_validator import (
    parse_uploaded_log_content,
    parse_uploaded_runbook_content,
    validate_evidence_availability,
    validate_uploaded_log_file,
    validate_uploaded_runbook_file,
    UploadValidationError,
)


class UploadedEvidence:
    """Container for validated uploaded evidence.

    Attributes:
        log_entries: Parsed log entries from all uploaded log files
        runbook_lines: Parsed runbook lines (filename, line_number, content)
        log_filenames: List of original log filenames
        runbook_filenames: List of original runbook filenames
    """

    def __init__(self):
        self.log_entries: List[LogEntry] = []
        self.runbook_lines: List[Tuple[str, int, str]] = []
        self.log_filenames: List[str] = []
        self.runbook_filenames: List[str] = []

    def add_log_file(self, filename: str, entries: List[LogEntry]) -> None:
        """Add parsed log entries from a file.

        Args:
            filename: Original filename
            entries: Parsed LogEntry objects
        """
        self.log_entries.extend(entries)
        if entries:  # Only add filename if we got valid entries
            self.log_filenames.append(filename)

    def add_runbook_file(
        self, filename: str, indexed_lines: List[Tuple[int, str]]
    ) -> None:
        """Add parsed runbook lines from a file.

        Args:
            filename: Original filename
            indexed_lines: List of (line_number, content) tuples
        """
        for line_number, content in indexed_lines:
            self.runbook_lines.append((filename, line_number, content))
        if indexed_lines:  # Only add filename if we got valid lines
            self.runbook_filenames.append(filename)

    def has_evidence(self) -> bool:
        """Check if any evidence was successfully loaded.

        Returns:
            True if at least one log entry or runbook line exists
        """
        return len(self.log_entries) > 0 or len(self.runbook_lines) > 0

    def get_summary(self) -> str:
        """Get a summary string of loaded evidence.

        Returns:
            Human-readable summary
        """
        log_count = len(self.log_entries)
        log_file_count = len(self.log_filenames)
        runbook_line_count = len(self.runbook_lines)
        runbook_file_count = len(self.runbook_filenames)

        parts = []
        if log_count > 0:
            parts.append(
                f"{log_count} log entries from {log_file_count} file(s)"
            )
        if runbook_line_count > 0:
            parts.append(
                f"{runbook_line_count} runbook lines from {runbook_file_count} file(s)"
            )

        return ", ".join(parts) if parts else "No evidence loaded"


def process_uploaded_logs(
    uploaded_files: list,
) -> Tuple[List[LogEntry], List[str], List[str]]:
    """Process uploaded log files and return parsed entries.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects

    Returns:
        Tuple of:
        - List of successfully parsed LogEntry objects
        - List of successfully processed filenames
        - List of error messages (empty if no errors)

    Note:
        Validates each file before parsing. Continues processing
        remaining files if one fails. Never raises exceptions.
    """
    all_entries: List[LogEntry] = []
    successful_filenames: List[str] = []
    errors: List[str] = []

    for uploaded_file in uploaded_files:
        try:
            # Read file content
            content = uploaded_file.read()
            file_size = len(content)
            filename = uploaded_file.name

            # Validate file
            is_valid, error_msg = validate_uploaded_log_file(
                filename, content, file_size
            )
            if not is_valid:
                errors.append(error_msg)
                continue

            # Parse content
            content_str = content.decode("utf-8")
            entries = parse_uploaded_log_content(content_str, filename)

            if not entries:
                errors.append(
                    f"File '{filename}': No valid log entries could be parsed"
                )
                continue

            all_entries.extend(entries)
            successful_filenames.append(filename)

        except Exception as e:
            # Catch any unexpected errors and provide safe message
            error_type = type(e).__name__
            errors.append(
                f"File '{uploaded_file.name}': Processing failed ({error_type})"
            )

    return all_entries, successful_filenames, errors


def process_uploaded_runbooks(
    uploaded_files: list,
) -> Tuple[List[Tuple[str, int, str]], List[str], List[str]]:
    """Process uploaded runbook files and return parsed lines.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects

    Returns:
        Tuple of:
        - List of (filename, line_number, content) tuples
        - List of successfully processed filenames
        - List of error messages (empty if no errors)

    Note:
        Validates each file before parsing. Continues processing
        remaining files if one fails. Never raises exceptions.
    """
    all_lines: List[Tuple[str, int, str]] = []
    successful_filenames: List[str] = []
    errors: List[str] = []

    for uploaded_file in uploaded_files:
        try:
            # Read file content
            content = uploaded_file.read()
            file_size = len(content)
            filename = uploaded_file.name

            # Validate file
            is_valid, error_msg = validate_uploaded_runbook_file(
                filename, content, file_size
            )
            if not is_valid:
                errors.append(error_msg)
                continue

            # Parse content
            content_str = content.decode("utf-8")
            indexed_lines = parse_uploaded_runbook_content(content_str, filename)

            if not indexed_lines:
                errors.append(
                    f"File '{filename}': No valid runbook lines could be parsed"
                )
                continue

            for line_number, line_content in indexed_lines:
                all_lines.append((filename, line_number, line_content))

            successful_filenames.append(filename)

        except Exception as e:
            # Catch any unexpected errors and provide safe message
            error_type = type(e).__name__
            errors.append(
                f"File '{uploaded_file.name}': Processing failed ({error_type})"
            )

    return all_lines, successful_filenames, errors


def create_evidence_retriever_from_uploads(
    log_entries: List[LogEntry],
    runbook_lines: List[Tuple[str, int, str]],
) -> EvidenceRetriever:
    """Create evidence retriever from uploaded files.

    Args:
        log_entries: Parsed log entries
        runbook_lines: List of (filename, line_number, content) tuples

    Returns:
        Ready-to-use EvidenceRetriever instance

    Note:
        All processing happens in-memory. Original filenames and
        line numbers are preserved for evidence citations.
    """
    retriever = EvidenceRetriever()

    # Index log entries
    retriever.index_log_entries(log_entries)

    # Index runbook lines
    for filename, line_number, content in runbook_lines:
        retriever.corpus.append(content)
        retriever.evidence_metadata.append(
            {
                "source_file": filename,
                "source_type": "runbook",
                "line_number": line_number,
                "content": content,
            }
        )

    # Build index
    retriever.build_index()

    return retriever
