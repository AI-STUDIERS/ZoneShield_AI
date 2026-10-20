"""Decision Engine: Tier 1 policy, Tier 2 agent orchestration, state machine.

Integrates guardrails (G1-G5) as a final veto after both tiers.
Produces Decision objects with full traceability (AgentTrace).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from zoneshield.agent import AgentClient, AgentTrace, ToolCall
from zoneshield.guardrails import FireRequest, check_all_guardrails


class TrackState(Enum):
    """Per-track decision-engine state machine."""
    MONITORING = "monitoring"
    TRACKING = "tracking"
    ASSESSING = "assessing"
    GATHERING_EVIDENCE = "gathering_evidence"
    AWAITING_HUMAN = "awaiting_human"
    INTERCEPTING = "intercepting"
    VERIFYING = "verifying"


@dataclass(frozen=True)
class Decision:
    """Output of the Decision Engine."""
    id: str
    session_id: str
    track_id: int
    state_from: TrackState
    state_to: TrackState
    action: str  # monitor | gather_evidence | request_human | intercept
    tier: str  # 1 | 2 | human | guardrail
    confidence_before: float
    confidence_after: Optional[float]
    reason: str
    evidence_ids: list[str] = field(default_factory=list)
    trace_id: Optional[str] = None
    t_ms: float = 0.0
    guardrail_veto: Optional[str] = None  # G1-G5 if vetoed, None otherwise


class Tier1Policy:
    """Fast Tier 1 policy. Runs inside the frame budget."""

    def __init__(self, t_intercept: float = 0.75, t_ambiguous_low: float = 0.40) -> None:
        self._t_intercept = t_intercept
        self._t_ambiguous_low = t_ambiguous_low

    def evaluate(
        self,
        confidence: float,
        tti_ms: Optional[float],
        crosses_zone: bool,
        jet_aligned: bool,
    ) -> tuple[str, Optional[str]]:
        """Return (action, reason). Action: intercept | monitor | tier2."""
        if confidence >= self._t_intercept and tti_ms is not None and crosses_zone and jet_aligned:
            return "intercept", f"confidence={confidence:.2f} >= {self._t_intercept}, TTI feasible, jet aligned"
        if confidence < self._t_ambiguous_low:
            return "monitor", f"confidence={confidence:.2f} < ambiguous threshold {self._t_ambiguous_low:.2f}"
        return "tier2", f"confidence={confidence:.2f} in ambiguous zone; escalating to Tier 2"


class DecisionEngine:
    """Orchestrates Tier 1, Tier 2 agent, and guardrails.

    Flow per track:
      1. Assess track + prediction + risk
      2. Tier 1 policy (fast, < frame budget)
      3. If Tier 1 says tier2 -> invoke Tier 2 agent (time-budgeted by TTI)
      4. Apply guardrails (G1-G5) — final veto
      5. Emit Decision with state transition and AgentTrace
    """

    def __init__(
        self,
        agent_client: AgentClient,
        t_intercept: float = 0.75,
        t_ambiguous_low: float = 0.40,
        actuation_delay_ms: float = 80.0,
        min_tti_margin_ms: float = 150.0,
        agent_max_steps: int = 4,
        agent_timeout_ms: float = 2000.0,
    ) -> None:
        self._agent = agent_client
        self._tier1 = Tier1Policy(t_intercept, t_ambiguous_low)
        self._actuation_delay_ms = actuation_delay_ms
        self._min_tti_margin_ms = min_tti_margin_ms
        self._agent_max_steps = agent_max_steps
        self._agent_timeout_ms = agent_timeout_ms
        self._decision_counter = 0
        self._track_states: dict[int, TrackState] = {}

    def _next_decision_id(self) -> str:
        self._decision_counter += 1
        return f"dec_{self._decision_counter:06d}"

    def _track_state(self, track_id: int) -> TrackState:
        return self._track_states.get(track_id, TrackState.MONITORING)

    def _set_track_state(self, track_id: int, state: TrackState) -> None:
        self._track_states[track_id] = state

    def evaluate(
        self,
        session_id: str,
        track_id: int,
        confidence: float,
        class_probs: dict,
        tti_ms: Optional[float],
        crosses_zone: bool,
        jet_aligned: bool,
        thresholds: dict,
        evidence_round: int = 0,
    ) -> Decision:
        """Run the full decision pipeline for one track."""
        start_ms = time.perf_counter() * 1000.0
        decision_id = self._next_decision_id()
        state_from = self._track_state(track_id)

        tier1_action, tier1_reason = self._tier1.evaluate(
            confidence, tti_ms, crosses_zone, jet_aligned
        )

        trace = AgentTrace(decision_id=decision_id, model_id=self._agent.model_id)
        tier = "1"
        action = tier1_action
        reason = tier1_reason
        confidence_after = confidence
        evidence_ids: list[str] = []

        if tier1_action == "tier2":
            tier = "2"
            time_budget_ms = self._compute_agent_time_budget(tti_ms)
            if time_budget_ms <= 0:
                action = "monitor"
                reason = f"TTI budget too small ({time_budget_ms:.0f}ms); skipping agent, safe monitor"
                tier = "1"
                trace.fallback_used = True
                trace.fallback_reason = "tti_budget_too_small"
            elif not self._agent.is_available():
                action = "monitor"
                reason = "Agent unavailable; safe monitor fallback"
                tier = "1"
                trace.fallback_used = True
                trace.fallback_reason = "agent_unavailable"
            else:
                context = {
                    "track": {"id": track_id, "confidence": confidence, **class_probs},
                    "prediction": {"tti_ms": tti_ms, "crosses_zone": crosses_zone},
                    "risk": {},
                    "thresholds": thresholds,
                    "evidence_round": evidence_round,
                }
                step_count = 0
                while step_count < self._agent_max_steps:
                    step_count += 1
                    try:
                        tool_call = self._agent.decide(context, time_budget_ms, trace)
                    except Exception as exc:
                        trace.fallback_used = True
                        trace.fallback_reason = f"agent_exception:{exc}"
                        action = "monitor"
                        reason = "Agent exception; safe monitor"
                        break

                    if tool_call.name == "intercept":
                        action = "intercept"
                        reason = tool_call.result_summary
                        confidence_after = min(1.0, confidence + tool_call.confidence_delta)
                        evidence_ids = tool_call.evidence_ids
                        break
                    if tool_call.name == "monitor":
                        action = "monitor"
                        reason = tool_call.result_summary
                        confidence_after = confidence
                        evidence_ids = tool_call.evidence_ids
                        break
                    if tool_call.name == "escalate_human":
                        action = "request_human"
                        reason = tool_call.result_summary
                        confidence_after = confidence
                        evidence_ids = tool_call.evidence_ids
                        break
                    if tool_call.name == "request_more_frames":
                        # Agent needs more visual evidence; caller collects frames
                        # and re-invokes evaluate() with updated confidence.
                        action = "gather_evidence"
                        reason = tool_call.result_summary
                        confidence_after = min(1.0, confidence + tool_call.confidence_delta)
                        evidence_ids = tool_call.evidence_ids
                        break
                    if tool_call.name == "fallback":
                        action = "monitor"
                        reason = tool_call.result_summary
                        confidence_after = confidence
                        trace.fallback_used = True
                        trace.fallback_reason = tool_call.args.get("reason", "unknown")
                        break
                    action = "monitor"
                    reason = f"Unknown tool {tool_call.name}; safe monitor"
                    trace.fallback_used = True
                    trace.fallback_reason = f"unknown_tool:{tool_call.name}"
                    break
                else:
                    action = "request_human"
                    reason = "Max agent steps reached without resolution"
        else:
            confidence_after = confidence

        # ---- Guardrails (final veto) ----
        if action == "intercept":
            req = FireRequest(
                tti_ms=tti_ms if tti_ms is not None else 0.0,
                actuation_delay_ms=self._actuation_delay_ms,
                min_tti_margin_ms=self._min_tti_margin_ms,
                predicted_x_at_jet=0.0,
                jet_cone_center_x=0.0,
                jet_cone_half_width=0.0,
                confidence=confidence_after,
                t_ambiguous_low=self._tier1._t_ambiguous_low,
                last_fire_ms=0.0,
                now_ms=start_ms,
                cooldown_ms=500.0,
                kill_switch_enabled=False,
            )
            veto = check_all_guardrails(req)
            if veto.blocked:
                action = "monitor"
                tier = "guardrail"
                reason = f"Guardrail {veto.guardrail} vetoed intercept: {veto.reason}"
                confidence_after = confidence
                trace.fallback_used = True
                trace.fallback_reason = f"{veto.guardrail}:{veto.reason}"

        # ---- State transition ----
        state_to = self._next_state(state_from, action)
        self._set_track_state(track_id, state_to)

        t_ms = (time.perf_counter() * 1000.0 - start_ms)
        trace.completed = True

        return Decision(
            id=decision_id,
            session_id=session_id,
            track_id=track_id,
            state_from=state_from,
            state_to=state_to,
            action=action,
            tier=tier,
            confidence_before=confidence,
            confidence_after=confidence_after,
            reason=reason,
            evidence_ids=evidence_ids,
            trace_id=decision_id,
            t_ms=t_ms,
            guardrail_veto=None if tier != "guardrail" else tier,
        )

    def _compute_agent_time_budget(self, tti_ms: Optional[float]) -> float:
        if tti_ms is None:
            return 0.0
        budget = tti_ms - self._actuation_delay_ms - self._min_tti_margin_ms
        return max(0.0, budget)

    def _next_state(self, current: TrackState, action: str) -> TrackState:
        transitions = {
            TrackState.MONITORING: {
                "monitor": TrackState.MONITORING,
                "gather_evidence": TrackState.GATHERING_EVIDENCE,
                "request_human": TrackState.AWAITING_HUMAN,
                "intercept": TrackState.INTERCEPTING,
            },
            TrackState.TRACKING: {
                "monitor": TrackState.MONITORING,
                "gather_evidence": TrackState.GATHERING_EVIDENCE,
                "request_human": TrackState.AWAITING_HUMAN,
                "intercept": TrackState.INTERCEPTING,
            },
            TrackState.ASSESSING: {
                "monitor": TrackState.MONITORING,
                "gather_evidence": TrackState.GATHERING_EVIDENCE,
                "request_human": TrackState.AWAITING_HUMAN,
                "intercept": TrackState.INTERCEPTING,
            },
            TrackState.GATHERING_EVIDENCE: {
                "monitor": TrackState.MONITORING,
                "gather_evidence": TrackState.GATHERING_EVIDENCE,
                "request_human": TrackState.AWAITING_HUMAN,
                "intercept": TrackState.INTERCEPTING,
            },
            TrackState.AWAITING_HUMAN: {
                "monitor": TrackState.MONITORING,
                "request_human": TrackState.AWAITING_HUMAN,
                "intercept": TrackState.INTERCEPTING,
            },
            TrackState.INTERCEPTING: {
                "monitor": TrackState.VERIFYING,
                "intercept": TrackState.VERIFYING,
            },
            TrackState.VERIFYING: {
                "monitor": TrackState.MONITORING,
            },
        }
        return transitions.get(current, {}).get(action, TrackState.MONITORING)

    def get_track_state(self, track_id: int) -> TrackState:
        return self._track_state(track_id)

    def get_agent_model_id(self) -> str:
        return self._agent.model_id