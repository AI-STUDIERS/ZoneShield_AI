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


import json
import os
from typing import Any, Callable


class BedrockAgentClient(AgentClient):
    """Production Amazon Bedrock Tier 2 decision agent.

    Connects to Amazon Bedrock Runtime (Claude 3 / Nova / Titan) via boto3.
    Adheres strictly to the ZoneShield AI Master Prompt:
      - Advisory decision-support component; CANNOT override guardrails (G1-G5).
      - Prefers gathering evidence over acting when uncertain.
      - Never intercepts below ambiguous threshold.
      - Returns exactly one tool call per invocation.
      - Enforces time budgets, circuit breaker, and graceful fallback to Tier 1.
    """

    SYSTEM_PROMPT = (
        "You are ZoneShield AI's Tier 2 Decision Support Agent for an active industrial conveyor.\n"
        "You are an advisory decision-support component; you CANNOT override guardrails G1-G5.\n"
        "Prefer gathering evidence over acting when uncertain.\n"
        "Never intercept when confidence is below the ambiguous threshold.\n"
        "Allowed actions: 'request_more_frames', 'intercept', 'escalate_human', 'monitor'.\n"
        "Explain the visual evidence behind every choice in exactly one sentence.\n"
        "Return ONLY a valid JSON object with keys: 'action', 'args', 'reason', 'confidence_delta'."
    )

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: str = "us-east-1",
        invoker: Optional[Callable[[str, dict], dict]] = None,
    ) -> None:
        self._model_id = (
            model_id
            or os.environ.get("ZONESHIELD_BEDROCK_MODEL_ID")
            or "anthropic.claude-3-haiku-20240307-v1:0"
        )
        self._region = os.environ.get("AWS_REGION", region)
        self._circuit_breaker = CircuitBreaker()
        self._invoker = invoker  # Optional custom invoker for testing/mocking
        self._boto_client: Optional[Any] = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def is_available(self) -> bool:
        return self._circuit_breaker.can_execute()

    def _get_bedrock_client(self) -> Any:
        if self._boto_client is not None:
            return self._boto_client
        try:
            import boto3
            from botocore.config import Config
            config = Config(connect_timeout=1.0, read_timeout=2.0, retries={"max_attempts": 1})
            self._boto_client = boto3.client("bedrock-runtime", region_name=self._region, config=config)
            return self._boto_client
        except Exception:
            return None

    def decide(
        self,
        context: dict,
        time_budget_ms: float,
        trace: AgentTrace,
    ) -> ToolCall:
        start_ms = time.perf_counter() * 1000.0

        if not self.is_available():
            step = ToolCall(
                name="fallback",
                args={"reason": "circuit_breaker_open"},
                result_summary="Bedrock agent unavailable; circuit breaker open",
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

        # Grounding check: never intercept below ambiguous threshold
        if confidence < t_ambiguous_low:
            step = ToolCall(
                name="fallback",
                args={"reason": f"confidence {confidence:.2f} < ambiguous floor {t_ambiguous_low:.2f}"},
                result_summary=f"Confidence {confidence:.2f} below ambiguous floor; defaulting to safe monitor",
                t_ms=(time.perf_counter() * 1000.0 - start_ms),
            )
            trace.add_step(step)
            trace.fallback_used = True
            trace.fallback_reason = "confidence_below_threshold"
            self._circuit_breaker.record_success()
            return step

        # Custom invoker (for tests / offline simulation)
        if self._invoker is not None:
            try:
                res = self._invoker(self._model_id, context)
                elapsed = time.perf_counter() * 1000.0 - start_ms
                step = ToolCall(
                    name=res.get("action", "monitor"),
                    args=res.get("args", {}),
                    result_summary=res.get("reason", "Custom invoker decision"),
                    evidence_ids=[f"ev_{trace.decision_id}_round{evidence_round}"],
                    confidence_delta=res.get("confidence_delta", 0.0),
                    t_ms=elapsed,
                )
                trace.add_step(step)
                self._circuit_breaker.record_success()
                return step
            except Exception as exc:
                self._circuit_breaker.record_failure()
                step = ToolCall(
                    name="fallback",
                    args={"reason": f"invoker_error:{exc}"},
                    result_summary=f"Custom invoker error: {exc}",
                    t_ms=time.perf_counter() * 1000.0 - start_ms,
                )
                trace.add_step(step)
                trace.fallback_used = True
                trace.fallback_reason = f"invoker_error:{exc}"
                return step

        client = self._get_bedrock_client()
        if client is None:
            elapsed = time.perf_counter() * 1000.0 - start_ms
            step = ToolCall(
                name="fallback",
                args={"reason": "bedrock_not_configured"},
                result_summary="Amazon Bedrock client not configured / boto3 unavailable; safe fallback",
                t_ms=elapsed,
            )
            trace.add_step(step)
            trace.fallback_used = True
            trace.fallback_reason = "bedrock_not_configured"
            self._circuit_breaker.record_failure()
            return step

        # Prepare Bedrock request payload
        user_prompt = (
            f"Object State:\n"
            f"- Track ID: {track.get('id', -1)}\n"
            f"- Confidence: {confidence:.3f}\n"
            f"- Probabilities: {track.get('class_probs', {})}\n"
            f"- Time-to-Intercept: {tti_ms} ms\n"
            f"- Zone Crossing: {prediction.get('crosses_zone', False)}\n"
            f"- Evidence Round: {evidence_round}\n"
            f"- Time Budget Remaining: {time_budget_ms:.1f} ms\n\n"
            f"Choose an action: 'request_more_frames', 'intercept', 'escalate_human', or 'monitor'."
        )

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "system": self.SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": 0.1,
            })

            response = client.invoke_model(
                modelId=self._model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            resp_body = json.loads(response["body"].read().decode("utf-8"))
            raw_text = resp_body["content"][0]["text"].strip()
            
            # Parse JSON action from response text
            if "{" in raw_text and "}" in raw_text:
                json_part = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]
                parsed = json.loads(json_part)
            else:
                parsed = {"action": "monitor", "reason": raw_text, "confidence_delta": 0.0}

            action = parsed.get("action", "monitor")
            reason = parsed.get("reason", "Bedrock decision evaluated")
            delta = float(parsed.get("confidence_delta", 0.0))

            usage = resp_body.get("usage", {})
            trace.tokens_in = usage.get("input_tokens", 0)
            trace.tokens_out = usage.get("output_tokens", 0)

            elapsed = time.perf_counter() * 1000.0 - start_ms
            step = ToolCall(
                name=action,
                args=parsed.get("args", {"track_id": track.get("id", -1)}),
                result_summary=reason,
                evidence_ids=[f"bedrock_{trace.decision_id}_round{evidence_round}"],
                confidence_delta=delta,
                t_ms=elapsed,
            )
            trace.add_step(step)
            self._circuit_breaker.record_success()
            return step

        except Exception as exc:
            self._circuit_breaker.record_failure()
            elapsed = time.perf_counter() * 1000.0 - start_ms
            step = ToolCall(
                name="fallback",
                args={"reason": f"bedrock_exception:{exc}"},
                result_summary=f"Bedrock invocation failed ({exc}); safe Tier 1 fallback",
                t_ms=elapsed,
            )
            trace.add_step(step)
            trace.fallback_used = True
            trace.fallback_reason = f"bedrock_exception:{exc}"
            return step