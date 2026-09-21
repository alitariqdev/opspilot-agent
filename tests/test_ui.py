"""Tests for UI presentation helpers."""

import pytest

from src.opspilot.models import (
    EvidenceChunk,
    HypothesisStatus,
    RemediationAction,
    RiskLevel,
    RootCauseHypothesis,
    Severity,
    TimelineEvent,
)
from src.opspilot.ui import format_hypothesis_status, format_severity_badge


def test_format_severity_badge_sev1():
    """Test SEV1 formatting."""
    result = format_severity_badge(Severity.SEV1)
    assert "SEV1" in result
    assert "Critical" in result


def test_format_severity_badge_sev2():
    """Test SEV2 formatting."""
    result = format_severity_badge(Severity.SEV2)
    assert "SEV2" in result
    assert "High" in result


def test_format_severity_badge_sev3():
    """Test SEV3 formatting."""
    result = format_severity_badge(Severity.SEV3)
    assert "SEV3" in result
    assert "Medium" in result


def test_format_severity_badge_sev4():
    """Test SEV4 formatting."""
    result = format_severity_badge(Severity.SEV4)
    assert "SEV4" in result
    assert "Low" in result


def test_format_hypothesis_status_supported():
    """Test supported status formatting."""
    result = format_hypothesis_status(HypothesisStatus.SUPPORTED)
    assert "Supported" in result


def test_format_hypothesis_status_partially_supported():
    """Test partially supported status formatting."""
    result = format_hypothesis_status(HypothesisStatus.PARTIALLY_SUPPORTED)
    assert "Partially" in result


def test_format_hypothesis_status_unsupported():
    """Test unsupported status formatting."""
    result = format_hypothesis_status(HypothesisStatus.UNSUPPORTED)
    assert "Unsupported" in result
