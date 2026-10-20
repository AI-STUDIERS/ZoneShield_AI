"""Guardrails (G1-G5) from the master prompt.

Pure functions with exhaustive unit tests. Every veto is a Decision with
tier=guardrail and a reason. Guardrails sit AFTER both tiers and can veto
any action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GuardrailVeto:
    """Result of a guardrail check."""
    blocked: bool
    reason: Optional[str] = None
    guardrail: Optional[str] = None  # G1..G5


@dataclass(frozen=True)
class FireRequest:
    """Request to fire the interceptor."""
    tti_ms: float
    actuation_delay_ms: float
    min_tti_margin_ms: float
    predicted_x_at_jet: float
    jet_cone_center_x: float
    jet_cone_half_width: float
    confidence: float
    t_ambiguous_low: float
    last_fire_ms: float
    now_ms: float
    cooldown_ms: float
    kill_switch_enabled: bool


def g1_tti_margin(req: FireRequest) -> GuardrailVeto:
    """G1: Never fire if TTI < actuation_delay + min_tti_margin_ms."""
    min_tti = req.actuation_delay_ms + req.min_tti_margin_ms
    if req.tti_ms < min_tti:
        return GuardrailVeto(
            blocked=True,
            reason=f"TTI {req.tti_ms:.1f}ms < min {min_tti:.1f}ms (delay+margin)",
            guardrail="G1",
        )
    return GuardrailVeto(blocked=False)


def g2_jet_cone(req: FireRequest) -> GuardrailVeto:
    """G2: Never fire if predicted lateral position at t_at_jet is outside jet cone."""
    left = req.jet_cone_center_x - req.jet_cone_half_width
    right = req.jet_cone_center_x + req.jet_cone_half_width
    if not (left <= req.predicted_x_at_jet <= right):
        return GuardrailVeto(
            blocked=True,
            reason=f"Predicted x {req.predicted_x_at_jet:.1f} outside cone [{left:.1f}, {right:.1f}]",
            guardrail="G2",
        )
    return GuardrailVeto(blocked=False)


def g3_ambiguous_threshold(req: FireRequest) -> GuardrailVeto:
    """G3: Never fire below t_ambiguous_low without approval or raised confidence."""
    if req.confidence < req.t_ambiguous_low:
        return GuardrailVeto(
            blocked=True,
            reason=f"Confidence {req.confidence:.2f} < ambiguous threshold {req.t_ambiguous_low:.2f}",
            guardrail="G3",
        )
    return GuardrailVeto(blocked=False)


def g4_cooldown(req: FireRequest) -> GuardrailVeto:
    """G4: Cooldown between firings."""
    if req.now_ms - req.last_fire_ms < req.cooldown_ms:
        return GuardrailVeto(
            blocked=True,
            reason=f"Cooldown: {(req.now_ms - req.last_fire_ms):.1f}ms < {req.cooldown_ms}ms",
            guardrail="G4",
        )
    return GuardrailVeto(blocked=False)


def g5_kill_switch(req: FireRequest) -> GuardrailVeto:
    """G5: Kill switch disables the actuator instantly."""
    if req.kill_switch_enabled:
        return GuardrailVeto(
            blocked=True,
            reason="Kill switch enabled",
            guardrail="G5",
        )
    return GuardrailVeto(blocked=False)


def check_all_guardrails(req: FireRequest) -> GuardrailVeto:
    """Run all guardrails in order. Return first veto or cleared."""
    for check in (g1_tti_margin, g2_jet_cone, g3_ambiguous_threshold, g4_cooldown, g5_kill_switch):
        result = check(req)
        if result.blocked:
            return result
    return GuardrailVeto(blocked=False)