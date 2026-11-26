"""Deterministic tests for the OPSFORGE Resilience scoring rules."""

from resilience_module import band, score_vendor


def test_vendor_score_uses_weighted_inputs():
    assert score_vendor(100, 100, 100, 100, 100) == 100
    assert score_vendor(0, 0, 0, 0, 0) == 0
    assert score_vendor(100, 0, 0, 0, 0) == 30


def test_vendor_risk_band_boundaries():
    assert band(0) == "LOW"
    assert band(29) == "LOW"
    assert band(30) == "MODERATE"
    assert band(49) == "MODERATE"
    assert band(50) == "HIGH"
    assert band(69) == "HIGH"
    assert band(70) == "CRITICAL"
    assert band(100) == "CRITICAL"
