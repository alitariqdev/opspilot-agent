"""Assignment 3: Comprehensive tests for calculate_service_metrics method.

This test file provides thorough coverage of the calculate_service_metrics
function, including edge cases, boundary conditions, and mathematical
properties of precision, recall, and F1 score calculations.
"""

import pytest

from src.opspilot.evaluation.metrics import calculate_service_metrics


class TestServiceMetricsIdenticalSets:
    """Tests for identical actual and expected sets."""

    def test_identical_single_service(self):
        """Test with identical single-service sets."""
        actual = {"api-gateway"}
        expected = {"api-gateway"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_identical_multiple_services(self):
        """Test with identical multi-service sets."""
        actual = {"api-gateway", "auth-service", "database"}
        expected = {"api-gateway", "auth-service", "database"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_identical_large_set(self):
        """Test with identical large sets (10 services)."""
        services = {f"service-{i}" for i in range(10)}
        actual = services.copy()
        expected = services.copy()

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0


class TestServiceMetricsPartialMatching:
    """Tests for partially matching sets."""

    def test_partial_one_correct_one_false_positive(self):
        """Test with one correct service and one false positive."""
        actual = {"service-a", "service-b"}
        expected = {"service-a"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == pytest.approx(0.5)  # 1/2
        assert metrics.recall == 1.0  # 1/1
        assert metrics.f1 == pytest.approx(2 / 3)  # 2 * 0.5 * 1.0 / (0.5 + 1.0)

    def test_partial_one_correct_one_false_negative(self):
        """Test with one correct service and one false negative."""
        actual = {"service-a"}
        expected = {"service-a", "service-b"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0  # 1/1
        assert metrics.recall == pytest.approx(0.5)  # 1/2
        assert metrics.f1 == pytest.approx(2 / 3)  # 2 * 1.0 * 0.5 / (1.0 + 0.5)

    def test_partial_two_correct_one_false_positive(self):
        """Test with two correct services and one false positive."""
        actual = {"service-a", "service-b", "service-c"}
        expected = {"service-a", "service-b"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == pytest.approx(2 / 3)  # 2/3
        assert metrics.recall == 1.0  # 2/2
        assert metrics.f1 == pytest.approx(0.8)  # 2 * (2/3) * 1.0 / (2/3 + 1.0)

    def test_partial_two_correct_one_false_negative(self):
        """Test with two correct services and one false negative."""
        actual = {"service-a", "service-b"}
        expected = {"service-a", "service-b", "service-c"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0  # 2/2
        assert metrics.recall == pytest.approx(2 / 3)  # 2/3
        assert metrics.f1 == pytest.approx(0.8)  # 2 * 1.0 * (2/3) / (1.0 + 2/3)

    def test_partial_one_correct_two_false_positives_two_false_negatives(self):
        """Test with one overlap, multiple false positives and negatives."""
        actual = {"service-a", "service-b", "service-c"}
        expected = {"service-a", "service-d", "service-e"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == pytest.approx(1 / 3)  # 1/3
        assert metrics.recall == pytest.approx(1 / 3)  # 1/3
        assert metrics.f1 == pytest.approx(1 / 3)  # 2 * (1/3) * (1/3) / (1/3 + 1/3)


class TestServiceMetricsDisjointSets:
    """Tests for completely disjoint sets with no overlap."""

    def test_disjoint_single_services(self):
        """Test with single disjoint services."""
        actual = {"service-a"}
        expected = {"service-b"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_disjoint_multiple_services(self):
        """Test with multiple disjoint services."""
        actual = {"service-a", "service-b", "service-c"}
        expected = {"service-x", "service-y", "service-z"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_disjoint_different_sizes(self):
        """Test with disjoint sets of different sizes."""
        actual = {"service-a", "service-b"}
        expected = {"service-x", "service-y", "service-z", "service-w"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0


class TestServiceMetricsEmptySets:
    """Tests for empty set edge cases."""

    def test_both_empty(self):
        """Test when both actual and expected are empty."""
        actual = set()
        expected = set()

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_actual_empty_expected_single(self):
        """Test when actual is empty and expected has one service."""
        actual = set()
        expected = {"service-a"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_actual_empty_expected_multiple(self):
        """Test when actual is empty and expected has multiple services."""
        actual = set()
        expected = {"service-a", "service-b", "service-c"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_expected_empty_actual_single(self):
        """Test when expected is empty and actual has one service."""
        actual = {"service-a"}
        expected = set()

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_expected_empty_actual_multiple(self):
        """Test when expected is empty and actual has multiple services."""
        actual = {"service-a", "service-b", "service-c"}
        expected = set()

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0


class TestServiceMetricsPrecisionCalculation:
    """Tests focusing on precision calculation (TP / (TP + FP))."""

    @pytest.mark.parametrize(
        "actual,expected,expected_precision",
        [
            ({"a"}, {"a"}, 1.0),  # 1/1
            ({"a", "b"}, {"a"}, 0.5),  # 1/2
            ({"a", "b", "c"}, {"a"}, 1 / 3),  # 1/3
            ({"a", "b", "c", "d"}, {"a"}, 0.25),  # 1/4
            ({"a", "b"}, {"a", "b"}, 1.0),  # 2/2
            ({"a", "b", "c"}, {"a", "b"}, 2 / 3),  # 2/3
            ({"a", "b", "c"}, {"a", "b", "c"}, 1.0),  # 3/3
        ],
    )
    def test_precision_various_false_positives(
        self, actual, expected, expected_precision
    ):
        """Test precision with varying numbers of false positives."""
        metrics = calculate_service_metrics(actual, expected)
        assert metrics.precision == pytest.approx(expected_precision)


class TestServiceMetricsRecallCalculation:
    """Tests focusing on recall calculation (TP / (TP + FN))."""

    @pytest.mark.parametrize(
        "actual,expected,expected_recall",
        [
            ({"a"}, {"a"}, 1.0),  # 1/1
            ({"a"}, {"a", "b"}, 0.5),  # 1/2
            ({"a"}, {"a", "b", "c"}, 1 / 3),  # 1/3
            ({"a"}, {"a", "b", "c", "d"}, 0.25),  # 1/4
            ({"a", "b"}, {"a", "b"}, 1.0),  # 2/2
            ({"a", "b"}, {"a", "b", "c"}, 2 / 3),  # 2/3
            ({"a", "b", "c"}, {"a", "b", "c"}, 1.0),  # 3/3
        ],
    )
    def test_recall_various_false_negatives(self, actual, expected, expected_recall):
        """Test recall with varying numbers of false negatives."""
        metrics = calculate_service_metrics(actual, expected)
        assert metrics.recall == pytest.approx(expected_recall)


class TestServiceMetricsF1Calculation:
    """Tests focusing on F1 score calculation (harmonic mean)."""

    def test_f1_perfect_score(self):
        """Test F1 when both precision and recall are 1.0."""
        actual = {"a", "b", "c"}
        expected = {"a", "b", "c"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.f1 == 1.0

    def test_f1_balanced_precision_recall(self):
        """Test F1 when precision and recall are equal but not 1.0."""
        actual = {"a", "b"}
        expected = {"a", "c"}

        metrics = calculate_service_metrics(actual, expected)

        # Precision: 1/2, Recall: 1/2
        # F1 = 2 * (0.5 * 0.5) / (0.5 + 0.5) = 0.5
        assert metrics.precision == 0.5
        assert metrics.recall == 0.5
        assert metrics.f1 == pytest.approx(0.5)

    def test_f1_high_precision_low_recall(self):
        """Test F1 with high precision and low recall."""
        actual = {"a"}
        expected = {"a", "b", "c", "d"}

        metrics = calculate_service_metrics(actual, expected)

        # Precision: 1/1 = 1.0, Recall: 1/4 = 0.25
        # F1 = 2 * (1.0 * 0.25) / (1.0 + 0.25) = 0.5 / 1.25 = 0.4
        assert metrics.precision == 1.0
        assert metrics.recall == 0.25
        assert metrics.f1 == pytest.approx(0.4)

    def test_f1_low_precision_high_recall(self):
        """Test F1 with low precision and high recall."""
        actual = {"a", "b", "c", "d"}
        expected = {"a"}

        metrics = calculate_service_metrics(actual, expected)

        # Precision: 1/4 = 0.25, Recall: 1/1 = 1.0
        # F1 = 2 * (0.25 * 1.0) / (0.25 + 1.0) = 0.5 / 1.25 = 0.4
        assert metrics.precision == 0.25
        assert metrics.recall == 1.0
        assert metrics.f1 == pytest.approx(0.4)

    def test_f1_zero_when_no_overlap(self):
        """Test F1 is zero when there is no overlap."""
        actual = {"a", "b"}
        expected = {"c", "d"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.f1 == 0.0

    @pytest.mark.parametrize(
        "actual,expected,expected_f1",
        [
            ({"a"}, {"a"}, 1.0),
            ({"a", "b"}, {"a"}, 2 / 3),
            ({"a"}, {"a", "b"}, 2 / 3),
            ({"a", "b", "c"}, {"a", "b"}, 0.8),
            ({"a", "b"}, {"a", "b", "c"}, 0.8),
        ],
    )
    def test_f1_symmetry_properties(self, actual, expected, expected_f1):
        """Test F1 symmetry: F1(A, B) = F1(B, A) when |A| = |B| ± 1."""
        metrics = calculate_service_metrics(actual, expected)
        assert metrics.f1 == pytest.approx(expected_f1)


class TestServiceMetricsRangeBounds:
    """Tests to ensure all metrics remain within [0.0, 1.0] bounds."""

    @pytest.mark.parametrize(
        "actual,expected",
        [
            (set(), set()),
            (set(), {"a"}),
            ({"a"}, set()),
            ({"a"}, {"a"}),
            ({"a"}, {"b"}),
            ({"a", "b"}, {"a"}),
            ({"a"}, {"a", "b"}),
            ({"a", "b", "c"}, {"x", "y", "z"}),
            ({"a", "b"}, {"a", "b"}),
            ({f"s{i}" for i in range(10)}, {f"s{i}" for i in range(5, 15)}),
        ],
    )
    def test_metrics_within_valid_range(self, actual, expected):
        """Test that all metrics stay within [0.0, 1.0] for various inputs."""
        metrics = calculate_service_metrics(actual, expected)

        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.f1 <= 1.0


class TestServiceMetricsHarmonicMeanProperty:
    """Tests to verify F1 is the harmonic mean of precision and recall."""

    @pytest.mark.parametrize(
        "actual,expected",
        [
            ({"a"}, {"a"}),
            ({"a", "b"}, {"a"}),
            ({"a"}, {"a", "b"}),
            ({"a", "b"}, {"a", "c"}),
            ({"a", "b", "c"}, {"a", "b"}),
            ({"a", "b"}, {"a", "b", "c"}),
            ({"a", "b", "c"}, {"a", "b", "d"}),
        ],
    )
    def test_f1_harmonic_mean_formula(self, actual, expected):
        """Test that F1 equals 2 * P * R / (P + R) for non-zero denominators."""
        metrics = calculate_service_metrics(actual, expected)

        if metrics.precision + metrics.recall > 0:
            expected_f1 = (
                2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall)
            )
            assert metrics.f1 == pytest.approx(expected_f1)
        else:
            assert metrics.f1 == 0.0


class TestServiceMetricsSpecialCases:
    """Tests for special cases and edge conditions."""

    def test_case_sensitive_service_names(self):
        """Test that service names are case-sensitive."""
        actual = {"Service-A", "service-b"}
        expected = {"service-a", "service-b"}

        metrics = calculate_service_metrics(actual, expected)

        # Only "service-b" matches (case-sensitive)
        assert metrics.precision == 0.5  # 1/2
        assert metrics.recall == 0.5  # 1/2
        assert metrics.f1 == pytest.approx(0.5)

    def test_whitespace_matters_in_service_names(self):
        """Test that whitespace in service names matters."""
        actual = {"service-a", "service-b "}
        expected = {"service-a", "service-b"}

        metrics = calculate_service_metrics(actual, expected)

        # Only "service-a" matches (whitespace difference)
        assert metrics.precision == 0.5  # 1/2
        assert metrics.recall == 0.5  # 1/2
        assert metrics.f1 == pytest.approx(0.5)

    def test_special_characters_in_service_names(self):
        """Test service names with special characters."""
        actual = {"api-gateway", "auth_service", "db.postgres"}
        expected = {"api-gateway", "auth_service", "db.postgres"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_unicode_service_names(self):
        """Test service names with unicode characters."""
        actual = {"service-α", "service-β"}
        expected = {"service-α", "service-β"}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_long_service_names(self):
        """Test with very long service names."""
        long_name = "very-long-service-name-" + "x" * 100
        actual = {long_name}
        expected = {long_name}

        metrics = calculate_service_metrics(actual, expected)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0


class TestServiceMetricsReturnType:
    """Tests to verify the return type and structure."""

    def test_returns_service_metrics_model(self):
        """Test that the function returns a ServiceMetrics instance."""
        from src.opspilot.evaluation.models import ServiceMetrics

        actual = {"service-a"}
        expected = {"service-a"}

        metrics = calculate_service_metrics(actual, expected)

        assert isinstance(metrics, ServiceMetrics)
        assert hasattr(metrics, "precision")
        assert hasattr(metrics, "recall")
        assert hasattr(metrics, "f1")

    def test_metrics_values_are_floats(self):
        """Test that all metric values are floats."""
        actual = {"service-a"}
        expected = {"service-a"}

        metrics = calculate_service_metrics(actual, expected)

        assert isinstance(metrics.precision, float)
        assert isinstance(metrics.recall, float)
        assert isinstance(metrics.f1, float)
