# ZoneShield AI - DECISIONS.md

## Assumptions and Open Questions

### COOL Integration (OPEN - C3)
- COOL (Cloud-Optimized OpenCV Library) delivery method and Python API not yet verified against official COOL docs.
- Assumption: COOL exposes a drop-in replacement or wrapper for cv2 functions (resize, adaptiveThreshold, findContours, morphology).
- Need to: Verify COOL install method on Graviton, confirm runtime activation proof, document the verification method.

### AWS Account and Credits (OPEN - C5)
- User asked us to ask before assuming anything about AWS account, credits, or COOL installation.
- Assumption: We will use mock mode (AGENT_MODE=mock) for local development and only deploy to AWS when credentials are provided.
- Need to: Confirm AWS region, instance types (c7g for Graviton, c7i for x86), credit budget.

### Bedrock Model ID (OPEN)
- ZONESHIELD_BEDROCK_MODEL_ID not set; must be verified for availability in chosen region.
- Assumption: Model ID will be provided via environment variable, never hardcoded.

### Classification Approach (DECIDED)
- Using classical color-based heuristic classifier (green-ish = foreign, blue-ish = legit) instead of DNN.
- Rationale: Master spec says "keep classical features" if cutting scope; DNN classifier is a cut candidate.
- Open question: Whether this meets precision/recall targets for evaluation.

### Simulator Physics (DECIDED)
- Constant belt velocity + lateral drift, no collision physics between objects.
- SimulatedActuator applies lateral impulse only if object is inside jet cone at fire time after actuation delay.
- Ground truth emitted per frame with class, position, intervention_required.

### Tracker (DECIDED)
- Kalman filter with constant-velocity model, nearest-centroid gating (50px threshold).
- Track kept for up to 5 missed frames before removal.

### Guardrails (DECIDED)
- G1-G5 implemented as pure functions with exhaustive unit tests.
- Guardrails checked in order: G1 (TTI margin), G2 (jet cone), G3 (ambiguous threshold), G4 (cooldown), G5 (kill switch).
- First veto wins.

### Repository Layout (DECIDED)
- Monorepo at zoneshield-ai/ with subpackages: vision, simulator, agent, backend, frontend, infra, benchmarks, eval, docs, scripts.
- Vision package contains the core OpenCV pipeline (zoneshield subpackage).