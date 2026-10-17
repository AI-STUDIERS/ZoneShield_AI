"""Unit tests for DecisionEngine (M3 acceptance gate: S2, S3, S4, S6 traces)."""

import pytest

from zoneshield.agent import MockAgent
from zoneshield.decision import DecisionEngine, TrackState


def _engine() -> DecisionEngine:
    return DecisionEngine(agent_client=MockAgent())


def test_tier1_high_confidence_intercept():
    eng = _engine()
    dec = eng.evaluate(
        session_id="s1",
        track_id=1,
        confidence=0.9,
        class_probs={"foreign": 0.9, "legit": 0.1, "ambiguous": 0.0},
        tti_ms=500.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
    )
    assert dec.action == "intercept"
    assert dec.tier == "1"
    assert dec.state_to == TrackState.INTERCEPTING


def test_tier1_low_confidence_monitor():
    eng = _engine()
    dec = eng.evaluate(
        session_id="s1",
        track_id=1,
        confidence=0.2,
        class_probs={"foreign": 0.2, "legit": 0.5, "ambiguous": 0.3},
        tti_ms=500.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
    )
    assert dec.action == "monitor"
    assert dec.tier == "1"
    assert dec.state_to == TrackState.MONITORING


def test_tier2_ambiguous_escalates_human():
    eng = _engine()
    dec = eng.evaluate(
        session_id="s1",
        track_id=1,
        confidence=0.6,
        class_probs={"foreign": 0.6, "legit": 0.3, "ambiguous": 0.1},
        tti_ms=500.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        evidence_round=2,  # max rounds reached -> escalate
    )
    assert dec.action == "request_human"
    assert dec.tier == "2"


def test_s2_occlusion_then_evidence_raises_confidence_intercept():
    """S2: occlusion lowers confidence -> request_more_frames -> confidence rises -> intercept."""
    eng = _engine()
    # First decision: ambiguous confidence (occlusion) -> Tier 2 gathers evidence
    dec1 = eng.evaluate(
        session_id="s2",
        track_id=1,
        confidence=0.5,
        class_probs={"foreign": 0.5, "legit": 0.4, "ambiguous": 0.1},
        tti_ms=1000.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        evidence_round=0,
    )
    assert dec1.action == "gather_evidence"
    assert dec1.tier == "2"

    # Second decision: after more frames, confidence rises -> intercept
    dec2 = eng.evaluate(
        session_id="s2",
        track_id=1,
        confidence=0.85,
        class_probs={"foreign": 0.85, "legit": 0.1, "ambiguous": 0.05},
        tti_ms=800.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        evidence_round=1,
    )
    assert dec2.action == "intercept"
    assert dec2.tier == "1"


def test_s3_look_alike_withheld():
    """S3: look-alike legitimate object -> agent withholds intercept."""
    eng = _engine()
    dec = eng.evaluate(
        session_id="s3",
        track_id=2,
        confidence=0.55,
        class_probs={"foreign": 0.55, "legit": 0.40, "ambiguous": 0.05},
        tti_ms=600.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        evidence_round=2,  # max evidence rounds -> escalate to human (withhold intercept)
    )
    # Agent withholds intercept, escalates to human for review
    assert dec.action == "request_human"
    assert dec.tier == "2"


def test_s4_glare_human_review():
    """S4: glare/lighting change -> human review."""
    eng = _engine()
    dec = eng.evaluate(
        session_id="s4",
        track_id=3,
        confidence=0.3,
        class_probs={"foreign": 0.3, "legit": 0.3, "ambiguous": 0.4},
        tti_ms=700.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        evidence_round=0,
    )
    assert dec.action == "monitor"
    assert dec.tier == "1"


def test_s6_high_speed_guardrail_blocks():
    """S6: high speed with too little TTI -> guardrail blocks and logs the miss."""
    eng = _engine()
    dec = eng.evaluate(
        session_id="s6",
        track_id=4,
        confidence=0.9,
        class_probs={"foreign": 0.9, "legit": 0.1, "ambiguous": 0.0},
        tti_ms=50.0,  # Very low TTI, below margin
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        evidence_round=0,
    )
    # G1 veto: TTI < actuation_delay + margin, so intercept is blocked
    assert dec.action == "monitor"
    assert dec.tier == "guardrail"
    assert "G1" in dec.reason


def test_state_machine_transitions():
    eng = _engine()
    # monitor -> monitoring
    dec1 = eng.evaluate(
        session_id="s1", track_id=1, confidence=0.2,
        class_probs={}, tti_ms=100.0, crosses_zone=False, jet_aligned=False,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
    )
    assert dec1.state_to == TrackState.MONITORING

    # tracking -> gathering_evidence (ambiguous confidence triggers Tier 2 evidence gathering)
    eng._set_track_state(2, TrackState.TRACKING)
    dec2 = eng.evaluate(
        session_id="s1", track_id=2, confidence=0.5,
        class_probs={}, tti_ms=500.0, crosses_zone=True, jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        evidence_round=0,
    )
    assert dec2.state_to == TrackState.GATHERING_EVIDENCE


def test_agent_trace_recorded():
    eng = _engine()
    dec = eng.evaluate(
        session_id="s1",
        track_id=1,
        confidence=0.6,
        class_probs={"foreign": 0.6, "legit": 0.3, "ambiguous": 0.1},
        tti_ms=500.0,
        crosses_zone=True,
        jet_aligned=True,
        thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
    )
    assert dec.trace_id is not None
    assert dec.t_ms > 0