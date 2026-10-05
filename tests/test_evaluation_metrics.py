"""Tests for evaluation metrics calculation."""

import pytest

from src.opspilot.evaluation.metrics import (
    calculate_diagnosis_metrics,
    calculate_rejected_claim_rate,
    calculate_service_metrics,
    extract_diagnosis_concepts,
    validate_evidence_citations,
)


class TestServiceMetrics:
    """Tests for service identification metrics."""

    def test_perfect_match(self):
        """Test metrics when actual matches expected perfectly."""
        actual = {"service-a", "service-b"}
        expected = {"service-a", "service-b"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_partial_match(self):
        """Test metrics with partial overlap."""
        actual = {"service-a", "service-b", "service-c"}
        expected = {"service-a", "service-b"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == pytest.approx(2 / 3)  # 2 correct out of 3 predicted
        assert metrics.recall == 1.0  # Found both expected
        assert metrics.f1 == pytest.approx(0.8)

    def test_no_match(self):
        """Test metrics with no overlap."""
        actual = {"service-a"}
        expected = {"service-b"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_empty_both(self):
        """Test metrics when both sets are empty."""
        metrics = calculate_service_metrics(set(), set())

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_empty_actual(self):
        """Test metrics when actual is empty but expected is not."""
        actual = set()
        expected = {"service-a"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_empty_expected(self):
        """Test metrics when expected is empty but actual is not."""
        actual = {"service-a"}
        expected = set()

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0


class TestDiagnosisMetrics:
    """Tests for diagnosis concept metrics."""

    def test_perfect_match(self):
        """Test metrics when concepts match perfectly."""
        actual = {"connection", "pool", "exhausted"}
        expected = {"connection", "pool", "exhausted"}

        metrics = calculate_diagnosis_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0

    def test_partial_match(self):
        """Test metrics with partial overlap."""
        actual = {"connection", "pool", "exhausted", "timeout"}
        expected = {"connection", "pool", "database"}

        metrics = calculate_diagnosis_metrics(actual, expected)

        assert metrics.precision == 0.5  # 2 relevant out of 4 predicted
        assert metrics.recall == pytest.approx(2 / 3)  # 2 relevant out of 3 expected

    def test_no_match(self):
        """Test metrics with no overlap."""
        actual = {"network"}
        expected = {"database"}

        metrics = calculate_diagnosis_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0

    def test_empty_both(self):
        """Test metrics when both sets are empty."""
        metrics = calculate_diagnosis_metrics(set(), set())

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0


class TestExtractDiagnosisConcepts:
    """Tests for diagnosis concept extraction."""

    def test_extract_simple_concepts(self):
        """Test extracting concepts from simple text."""
        text = "Database connection pool exhausted"
        concepts = extract_diagnosis_concepts(text)

        assert "database" in concepts
        assert "connection" in concepts
        assert "pool" in concepts
        assert "exhausted" in concepts

    def test_removes_stop_words(self):
        """Test that stop words are removed."""
        text = "The database is the connection pool"
        concepts = extract_diagnosis_concepts(text)

        assert "the" not in concepts
        assert "is" not in concepts
        assert "database" in concepts
        assert "connection" in concepts
        assert "pool" in concepts

    def test_lowercases_words(self):
        """Test that words are converted to lowercase."""
        text = "DATABASE Connection POOL"
        concepts = extract_diagnosis_concepts(text)

        assert "database" in concepts
        assert "connection" in concepts
        assert "pool" in concepts
        assert "DATABASE" not in concepts

    def test_handles_punctuation(self):
        """Test handling of punctuation."""
        text = "Connection-pool, exhausted! Timeout?"
        concepts = extract_diagnosis_concepts(text)

        assert "connection" in concepts
        assert "pool" in concepts
        assert "exhausted" in concepts
        assert "timeout" in concepts

    def test_filters_short_words(self):
        """Test that very short words are filtered."""
        text = "a is to be connection pool"
        concepts = extract_diagnosis_concepts(text)

        assert "connection" in concepts
        assert "pool" in concepts
        # Short words and stop words removed
        assert "a" not in concepts
        assert "is" not in concepts
        assert "to" not in concepts


class TestValidateEvidenceCitations:
    """Tests for evidence citation validation."""

    def test_all_valid(self):
        """Test when all citations are valid."""
        cited = ["ev_001", "ev_002", "ev_003"]
        available = {"ev_001", "ev_002", "ev_003", "ev_004"}

        validity = validate_evidence_citations(cited, available)

        assert validity == 1.0

    def test_partial_valid(self):
        """Test when some citations are invalid."""
        cited = ["ev_001", "ev_002", "ev_999"]
        available = {"ev_001", "ev_002", "ev_003"}

        validity = validate_evidence_citations(cited, available)

        assert validity == pytest.approx(2 / 3)

    def test_none_valid(self):
        """Test when no citations are valid."""
        cited = ["ev_999", "ev_888"]
        available = {"ev_001", "ev_002"}

        validity = validate_evidence_citations(cited, available)

        assert validity == 0.0

    def test_empty_citations(self):
        """Test when no citations provided (vacuously true)."""
        cited = []
        available = {"ev_001", "ev_002"}

        validity = validate_evidence_citations(cited, available)

        assert validity == 1.0


class TestRejectedClaimRate:
    """Tests for rejected claim rate calculation."""

    def test_all_rejected(self):
        """Test when all expected claims are rejected."""
        rejected = {"hardware", "network", "security"}
        expected = {"hardware", "network"}

        rate = calculate_rejected_claim_rate(rejected, expected)

        assert rate == 1.0

    def test_partial_rejected(self):
        """Test when some expected claims are rejected."""
        rejected = {"hardware"}
        expected = {"hardware", "network"}

        rate = calculate_rejected_claim_rate(rejected, expected)

        assert rate == 0.5

    def test_none_rejected(self):
        """Test when no expected claims are rejected."""
        rejected = {"database"}
        expected = {"hardware", "network"}

        rate = calculate_rejected_claim_rate(rejected, expected)

        assert rate == 0.0

    def test_no_expected_rejections(self):
        """Test when no rejections expected (vacuously true)."""
        rejected = {"hardware"}
        expected = set()

        rate = calculate_rejected_claim_rate(rejected, expected)

        assert rate == 1.0


class TestMetricEdgeCases:
    """Tests for edge cases in metric calculation."""

    def test_service_metrics_single_item(self):
        """Test service metrics with single item."""
        actual = {"service-a"}
        expected = {"service-a"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_diagnosis_concepts_case_insensitive(self):
        """Test that diagnosis is case-insensitive."""
        actual = {"Database", "CONNECTION"}
        expected = {"database", "connection"}

        # Concepts should be normalized to lowercase before comparison
        actual_normalized = {c.lower() for c in actual}
        expected_normalized = {c.lower() for c in expected}

        metrics = calculate_diagnosis_metrics(actual_normalized, expected_normalized)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0

    def test_evidence_citation_duplicates(self):
        """Test citation validation with duplicate IDs."""
        cited = ["ev_001", "ev_001", "ev_002"]
        available = {"ev_001", "ev_002"}

        # All citations are valid (including duplicates)
        validity = validate_evidence_citations(cited, available)

        assert validity == 1.0
