"""Unit tests for MockAgent, AgentTrace, CircuitBreaker (M3)."""

import time

import pytest

from zoneshield.agent import (
    AgentTrace,
    BedrockAgentClient,
    CircuitBreaker,
    MockAgent,
    ToolCall,
)


def test_tool_call_creation():
    tc = ToolCall(
        name="intercept",
        args={"track_id": 1},
        result_summary="intercepted",
        evidence_ids=["ev1"],
        confidence_delta=0.1,
        t_ms=5.0,
    )
    assert tc.name == "intercept"
    assert tc.confidence_delta == 0.1


def test_agent_trace_add_step():
    trace = AgentTrace(decision_id="dec_1")
    step = ToolCall(
        name="request_more_frames",
        args={"n_frames": 5},
        result_summary="requested frames",
        evidence_ids=["ev1"],
        t_ms=10.0,
    )
    trace.add_step(step)
    assert trace.step_count() == 1
    assert trace.latency_ms == 10.0


def test_agent_trace_to_dict():
    trace = AgentTrace(decision_id="dec_1", model_id="mock-agent:v1")
    step = ToolCall(name="monitor", args={}, result_summary="monitoring", t_ms=2.0)
    trace.add_step(step)
    d = trace.to_dict()
    assert d["decision_id"] == "dec_1"
    assert d["model_id"] == "mock-agent:v1"
    assert len(d["steps"]) == 1


def test_mock_agent_low_confidence_falls_back_to_tier1():
    agent = MockAgent()
    trace = AgentTrace(decision_id="dec_1")
    context = {
        "track": {"id": 1, "confidence": 0.2},
        "prediction": {"tti_ms": 1000.0, "crosses_zone": True},
        "thresholds": {"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        "evidence_round": 0,
    }
    tool = agent.decide(context, time_budget_ms=500.0, trace=trace)
    assert tool.name == "fallback"
    assert trace.fallback_used is True


def test_mock_agent_ambiguous_zone_requests_frames():
    agent = MockAgent()
    trace = AgentTrace(decision_id="dec_1")
    context = {
        "track": {"id": 1, "confidence": 0.5},
        "prediction": {"tti_ms": 1000.0, "crosses_zone": True},
        "thresholds": {"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        "evidence_round": 0,
    }
    tool = agent.decide(context, time_budget_ms=500.0, trace=trace)
    assert tool.name == "request_more_frames"
    assert trace.step_count() == 1


def test_mock_agent_high_confidence_intercepts():
    agent = MockAgent()
    trace = AgentTrace(decision_id="dec_1")
    context = {
        "track": {"id": 1, "confidence": 0.9},
        "prediction": {"tti_ms": 1000.0, "crosses_zone": True},
        "thresholds": {"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        "evidence_round": 0,
    }
    tool = agent.decide(context, time_budget_ms=500.0, trace=trace)
    assert tool.name == "intercept"


def test_mock_agent_ambiguous_escalates_after_max_rounds():
    agent = MockAgent()
    trace = AgentTrace(decision_id="dec_1")
    context = {
        "track": {"id": 1, "confidence": 0.6},
        "prediction": {"tti_ms": 1000.0, "crosses_zone": True},
        "thresholds": {"t_intercept": 0.75, "t_ambiguous_low": 0.40},
        "evidence_round": 2,  # max rounds reached
    }
    tool = agent.decide(context, time_budget_ms=500.0, trace=trace)
    assert tool.name == "escalate_human"


def test_mock_agent_model_id():
    agent = MockAgent()
    assert agent.model_id == "mock-agent:v1"


def test_circuit_breaker_opens_after_failures():
    cb = CircuitBreaker(failure_threshold=2, half_open_s=30.0)
    assert cb.can_execute() is True
    cb.record_failure()
    assert cb.can_execute() is True
    cb.record_failure()
    assert cb.can_execute() is False
    assert cb.state() == "open"


def test_circuit_breaker_half_open_after_timeout():
    cb = CircuitBreaker(failure_threshold=1, half_open_s=0.1)
    cb.record_failure()
    assert cb.can_execute() is False
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state() == "half-open"


def test_bedrock_agent_not_configured():
    agent = BedrockAgentClient()
    trace = AgentTrace(decision_id="dec_1")
    context = {"track": {}, "prediction": {}, "thresholds": {}, "evidence_round": 0}
    tool = agent.decide(context, time_budget_ms=500.0, trace=trace)
    assert tool.name == "fallback"
    assert trace.fallback_used is True