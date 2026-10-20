"""Unit tests for guardrails G1-G5 (M2 acceptance gate)."""

import pytest

from zoneshield.guardrails import (
    FireRequest,
    check_all_guardrails,
    g1_tti_margin,
    g2_jet_cone,
    g3_ambiguous_threshold,
    g4_cooldown,
    g5_kill_switch,
)


def _base_request(**overrides) -> FireRequest:
    defaults = dict(
        tti_ms=500.0,
        actuation_delay_ms=80.0,
        min_tti_margin_ms=150.0,
        predicted_x_at_jet=300.0,
        jet_cone_center_x=300.0,
        jet_cone_half_width=60.0,
        confidence=0.9,
        t_ambiguous_low=0.4,
        last_fire_ms=0.0,
        now_ms=10000.0,
        cooldown_ms=500.0,
        kill_switch_enabled=False,
    )
    defaults.update(overrides)
    return FireRequest(**defaults)


def test_g1_tti_margin_pass():
    req = _base_request(tti_ms=300.0)  # 300 >= 80+150=230
    assert not g1_tti_margin(req).blocked


def test_g1_tti_margin_fail():
    req = _base_request(tti_ms=200.0)  # 200 < 230
    v = g1_tti_margin(req)
    assert v.blocked
    assert v.guardrail == "G1"


def test_g2_jet_cone_pass():
    req = _base_request(predicted_x_at_jet=300.0)
    assert not g2_jet_cone(req).blocked


def test_g2_jet_cone_fail_outside():
    req = _base_request(predicted_x_at_jet=400.0)  # outside [240, 360]
    v = g2_jet_cone(req)
    assert v.blocked
    assert v.guardrail == "G2"


def test_g3_ambiguous_pass():
    req = _base_request(confidence=0.8)
    assert not g3_ambiguous_threshold(req).blocked


def test_g3_ambiguous_fail():
    req = _base_request(confidence=0.2)
    v = g3_ambiguous_threshold(req)
    assert v.blocked
    assert v.guardrail == "G3"


def test_g4_cooldown_pass():
    req = _base_request(last_fire_ms=0.0, now_ms=10000.0)
    assert not g4_cooldown(req).blocked


def test_g4_cooldown_fail():
    req = _base_request(last_fire_ms=9900.0, now_ms=10000.0)  # only 100ms ago, cooldown=500
    v = g4_cooldown(req)
    assert v.blocked
    assert v.guardrail == "G4"


def test_g5_kill_switch():
    req = _base_request(kill_switch_enabled=True)
    v = g5_kill_switch(req)
    assert v.blocked
    assert v.guardrail == "G5"


def test_check_all_guardrails_all_pass():
    req = _base_request()
    result = check_all_guardrails(req)
    assert not result.blocked


def test_check_all_guardrails_first_veto():
    # G1 fails first (tti=100 < 230)
    req = _base_request(tti_ms=100.0, kill_switch_enabled=True)
    result = check_all_guardrails(req)
    assert result.blocked
    assert result.guardrail == "G1"  # G1 checked first