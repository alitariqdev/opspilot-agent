"""Evidence retrieval using BM25 for OpsPilot."""

import hashlib
from pathlib import Path
from typing import List, Optional

from rank_bm25 import BM25Okapi

from src.opspilot.models import EvidenceChunk, LogEntry


def _generate_evidence_id(source_file: str, line_number: int) -> str:
    """Generate a stable evidence ID from source file and line number.

    Args:
        source_file: Source filename
        line_number: Line number in source

    Returns:
        Stable hash-based evidence identifier
    """
    content = f"{source_file}:{line_number}"
    hash_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"ev_{hash_digest[:16]}"


def _tokenize(text: str) -> List[str]:
    """Simple tokenization for BM25.

    Args:
        text: Text to tokenize

    Returns:
        List of lowercase tokens
    """
    return text.lower().split()


class EvidenceRetriever:
    """BM25-based evidence retriever for logs and runbooks.

    Indexes log entries and runbook content for local retrieval without
    external API calls.
    """

    def __init__(self):
        """Initialize empty evidence retriever."""
        self.corpus: List[str] = []
        self.evidence_metadata: List[dict] = []
        self.bm25: Optional[BM25Okapi] = None

    def index_log_entries(self, log_entries: List[LogEntry]) -> None:
        """Index parsed log entries for retrieval.

        Args:
            log_entries: List of parsed log entries to index
        """
        for entry in log_entries:
            # Combine timestamp, level, service, and message for searchability
            content = f"{entry.timestamp} {entry.level} {entry.service} {entry.message}"
            self.corpus.append(content)
            self.evidence_metadata.append(
                {
                    "source_file": entry.source_file,
                    "source_type": "log",
                    "line_number": entry.line_number,
                    "content": content,
                }
            )

    def index_runbook(self, runbook_path: Path) -> None:
        """Index a runbook markdown file for retrieval.

        Args:
            runbook_path: Path to the runbook file

        Note:
            Indexes only non-empty lines. Preserves line numbers.
        """
        if not runbook_path.exists():
            return

        source_filename = runbook_path.name

        with open(runbook_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if line:  # Only index non-empty lines
                    self.corpus.append(line)
                    self.evidence_metadata.append(
                        {
                            "source_file": source_filename,
                            "source_type": "runbook",
                            "line_number": line_number,
                            "content": line,
                        }
                    )

    def index_runbooks(self, runbook_directory: Path) -> None:
        """Index all runbooks in a directory.

        Args:
            runbook_directory: Directory containing runbook files
        """
        if not runbook_directory.exists():
            return

        for runbook_file in runbook_directory.glob("*.md"):
            if runbook_file.is_file():
                self.index_runbook(runbook_file)

    def build_index(self) -> None:
        """Build the BM25 index from the corpus.

        Must be called after indexing all documents and before retrieval.
        """
        if not self.corpus:
            self.bm25 = None
            return

        tokenized_corpus = [_tokenize(doc) for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def retrieve(self, query: str, top_k: int = 10) -> List[EvidenceChunk]:
        """Retrieve the most relevant evidence for a query.

        Args:
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of EvidenceChunk objects sorted by relevance score

        Note:
            Returns empty list if corpus is empty or query is empty.
        """
        if not query.strip():
            return []

        if not self.corpus or self.bm25 is None:
            return []

        tokenized_query = _tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices sorted by score
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]

        results: List[EvidenceChunk] = []
        for idx in top_indices:
            metadata = self.evidence_metadata[idx]
            evidence_id = _generate_evidence_id(
                metadata["source_file"], metadata["line_number"]
            )

            chunk = EvidenceChunk(
                evidence_id=evidence_id,
                source_file=metadata["source_file"],
                source_type=metadata["source_type"],
                line_number=metadata["line_number"],
                content=metadata["content"],
                score=float(scores[idx]),
            )
            results.append(chunk)

        return results


def create_evidence_retriever(
    log_entries: List[LogEntry],
    runbook_directory: Path,
) -> EvidenceRetriever:
    """Create and build an evidence retriever with logs and runbooks.

    Args:
        log_entries: Parsed log entries to index
        runbook_directory: Directory containing runbook markdown files

    Returns:
        Ready-to-use EvidenceRetriever instance
    """
    retriever = EvidenceRetriever()
    retriever.index_log_entries(log_entries)
    retriever.index_runbooks(runbook_directory)
    retriever.build_index()
    return retriever
