# M3 Design: Decision Engine, Agent, Review Queue

## Overview (M3: Oct 18-19)
Build the Decision Engine, state machine, Tier 2 agent (mock first), and review queue.
Gate: S2, S3, S4, S6 produce traces where evidence changes the decision.

## Components

### 1. AgentClient (abstract interface)
- `decide(context) -> ToolCall` — returns exactly one tool call from allowed set
- Allowed tools: `request_more_frames`, `gather_evidence`, `escalate_human`, `intercept`, `monitor`
- Max 4 steps per decision
- 2s timeout per call, 1 retry, circuit breaker (open after 3 failures, half-open after 30s)

### 2. MockAgent (deterministic, rule-based)
- Same interface as AgentClient
- Used for tests, CI, offline demos
- Logic: if confidence < t_ambiguous_low -> gather_evidence; if confidence >= t_intercept and timing feasible -> intercept; else -> escalate_human

### 3. BedrockAgentClient (stub)
- Interface ready for AWS Bedrock integration (M3+ / M5)
- Not wired until credentials confirmed

### 4. AgentTrace
- Records every step: tool name, args, result summary, evidence IDs, confidence delta, latency
- `fallback_used` flag when Tier 2 falls back to Tier 1

### 5. Decision Engine
- Tier 1 policy (fast, inside frame budget)
- Tier 2 agent (async, time-budgeted by TTI)
- State machine per track:
  MONITORING → TRACKING → ASSESSING → GATHERING_EVIDENCE → AWAITING_HUMAN → INTERCEPTING → VERIFYING
- Guardrails (G1-G5) veto after both tiers

### 6. Review Queue
- ReviewItem: pending with deadline, operator resolves or timeout
- Status: pending | approved | dismissed | more_evidence | expired

## Scenarios Covered (Gate)
- S2: occlusion lowers confidence → request_more_frames → confidence rises → intercept
- S3: look-alike legitimate object → agent withholds intercept
- S4: glare/lighting change → human review
- S6: high speed with too little TTI → guardrail blocks and logs the miss
