"""Agent interface and implementations for ZoneShield AI Tier 2 decision agent."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ToolCall:
    """Record of a single agent tool invocation."""
    name: str
    args: dict
    result_summary: str
    evidence_ids: list[str] = field(default_factory=list)
    confidence_delta: float = 0.0
    t_ms: float = 0.0


@dataclass
class AgentTrace:
    """Complete trace of agent reasoning for one decision."""
    decision_id: str
    steps: list[ToolCall] = field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    model_id: str = "mock"
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    completed: bool = False

    def add_step(self, step: ToolCall) -> None:
        self.steps.append(step)
        self.latency_ms += step.t_ms

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "steps": [
                {
                    "name": s.name,
                    "args": s.args,
                    "result_summary": s.result_summary,
                    "evidence_ids": s.evidence_ids,
                    "confidence_delta": s.confidence_delta,
                    "t_ms": s.t_ms,
                }
                for s in self.steps
            ],
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "model_id": self.model_id,
            "latency_ms": self.latency_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "completed": self.completed,
        }

    def step_count(self) -> int:
        return len(self.steps)

    def last_confidence_delta(self) -> float:
        if not self.steps:
            return 0.0
        return self.steps[-1].confidence_delta


class AgentClient(ABC):
    """Abstract Tier 2 agent interface. Mock and Bedrock implementations share this."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        ...

    @abstractmethod
    def decide(
        self,
        context: dict,
        time_budget_ms: float,
        trace: AgentTrace,
    ) -> ToolCall:
        """Return exactly one tool call from the allowed set."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the agent can accept new decisions."""
        ...


class CircuitBreaker:
    """Circuit breaker for agent resilience.

    Open after 3 consecutive failures, half-open after 30s.
    """

    def __init__(self, failure_threshold: int = 3, half_open_s: float = 30.0) -> None:
        self._failure_threshold = failure_threshold
        self._half_open_s = half_open_s
        self._failures = 0
        self._state = "closed"
        self._opened_at: Optional[float] = None

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._state = "open"
            self._opened_at = time.perf_counter()

    def can_execute(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if self._opened_at is not None and (time.perf_counter() - self._opened_at) > self._half_open_s:
                self._state = "half-open"
                return True
            return False
        return True

    def state(self) -> str:
        return self._state


class MockAgent(AgentClient):
    """Deterministic rule-based Tier 2 agent.

    Used for tests, CI, and offline demos. Same interface as BedrockAgentClient.
    Logic:
      - confidence < t_ambiguous_low  -> request_more_frames (gather evidence)
      - confidence >= t_intercept and timing feasible -> intercept
      - otherwise -> escalate_human
    Never intercepts below ambiguous threshold. Prefers gathering evidence.
    """

    def __init__(self) -> None:
        self._circuit_breaker = CircuitBreaker()
        self._decision_count = 0

    @property
    def model_id(self) -> str:
        return "mock-agent:v1"

    def is_available(self) -> bool:
        return self._circuit_breaker.can_execute()

    def decide(
        self,
        context: dict,
        time_budget_ms: float,
        trace: AgentTrace,
    ) -> ToolCall:
        self._decision_count += 1
        start_ms = time.perf_counter() * 1000.0

        if not self.is_available():
            step = ToolCall(
                name="fallback",
                args={"reason": "circuit_breaker_open"},
                result_summary="Agent unavailable; circuit breaker open",
                t_ms=0.0,
            )
            trace.add_step(step)
            trace.fallback_used = True
            trace.fallback_reason = "circuit_breaker_open"
            return step

        track = context.get("track", {})
        prediction = context.get("prediction", {})
        thresholds = context.get("thresholds", {})
        evidence_round = context.get("evidence_round", 0)

        t_intercept = thresholds.get("t_intercept", 0.75)
        t_ambiguous_low = thresholds.get("t_ambiguous_low", 0.40)
        confidence = track.get("confidence", 0.0)
        tti_ms = prediction.get("tti_ms")
        crosses_zone = prediction.get("crosses_zone", False)

        if confidence < t_ambiguous_low:
            step = ToolCall(
                name="fallback",
                args={"reason": f"confidence {confidence:.2f} below ambiguous threshold {t_ambiguous_low:.2f}; Tier 1 monitor"},
                result_summary=f"Confidence {confidence:.2f} below ambiguous threshold; deferring to Tier 1 monitor",
                t_ms=(time.perf_counter() * 1000.0 - start_ms),
            )
            trace.add_step(step)
            trace.fallback_used = True
            trace.fallback_reason = "confidence_below_threshold"
            self._circuit_breaker.record_success()
            return step

        if confidence >= t_intercept and tti_ms is not None and crosses_zone:
            step = ToolCall(
                name="intercept",
                args={"track_id": track.get("id", -1), "tti_ms": tti_ms},
                result_summary=f"Intercept authorized; confidence={confidence:.2f}, TTI={tti_ms:.0f}ms",
                evidence_ids=[],
                confidence_delta=0.0,
                t_ms=(time.perf_counter() * 1000.0 - start_ms),
            )
            trace.add_step(step)
            self._circuit_breaker.record_success()
            return step

        if evidence_round < 2:
            step = ToolCall(
                name="request_more_frames",
                args={"n_frames": 5, "reason": f"confidence {confidence:.2f} in ambiguous zone [{t_ambiguous_low:.2f}, {t_intercept:.2f})"},
                result_summary=f"Requested 5 more frames; confidence={confidence:.2f} in ambiguous zone",
                evidence_ids=[f"evidence_{trace.decision_id}_round{evidence_round + 1}"],
                confidence_delta=0.0,
                t_ms=(time.perf_counter() * 1000.0 - start_ms),
            )
            trace.add_step(step)
            self._circuit_breaker.record_success()
            return step

        step = ToolCall(
            name="escalate_human",
            args={"track_id": track.get("id", -1), "reason": "max evidence rounds reached without resolution"},
            result_summary=f"Escalated to human after {evidence_round} evidence rounds; confidence={confidence:.2f}",
            evidence_ids=[],
            confidence_delta=0.0,
            t_ms=(time.perf_counter() * 1000.0 - start_ms),
        )
        trace.add_step(step)
        self._circuit_breaker.record_success()
        return step


class BedrockAgentClient(AgentClient):
    """Stub for AWS Bedrock Tier 2 agent.

    Not yet wired; requires ZONESHIELD_BEDROCK_MODEL_ID and confirmed AWS
    credentials. Returns a fallback ToolCall until implemented.
    """

    def __init__(self, model_id: Optional[str] = None, region: str = "us-east-1") -> None:
        self._model_id = model_id or "bedrock-stub"
        self._region = region
        self._circuit_breaker = CircuitBreaker()

    @property
    def model_id(self) -> str:
        return self._model_id

    def is_available(self) -> bool:
        return self._circuit_breaker.can_execute()

    def decide(
        self,
        context: dict,
        time_budget_ms: float,
        trace: AgentTrace,
    ) -> ToolCall:
        step = ToolCall(
            name="fallback",
            args={"reason": "bedrock_not_configured"},
            result_summary="Bedrock agent not configured; falling back to Tier 1",
            t_ms=0.0,
        )
        trace.add_step(step)
        trace.fallback_used = True
        trace.fallback_reason = "bedrock_not_configured"
        self._circuit_breaker.record_failure()
        return step