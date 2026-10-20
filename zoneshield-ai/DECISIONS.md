# ZoneShield AI — Architecture & Design Decisions (DECISIONS.md)

This log records architectural decisions, assumptions, and resolution states for ZoneShield AI in compliance with Master Spec section 14.

---

## 1. Resolved Decisions

### [DECIDED] Actuator Digital Twin Simulation (C1 Hard Constraint)
- **Decision**: Strictly simulate the air-jet interceptor in software via `SimulatedActuator`.
- **Rationale**: Physical hardware is prohibited by C1. Actuation latency ($80\text{ ms}$), timing jitter ($10\text{ ms}$), physical jet cone geometry ($25^\circ$), and impulse dynamics are fully modeled in the digital twin. A non-tested `HardwareActuator` stub is provided for future physical integration.

### [DECIDED] OpenCV 5 & COOL Verification on Graviton (C2, C3, M5)
- **Decision**: Implement `zoneshield.selfcheck` CLI to verify OpenCV version, inspect `cv2.getBuildInformation()`, detect Arm64 / Graviton architecture, and verify Arm NEON / KleidiCV / COOL acceleration flags.
- **Artifact**: Emits structured verification proof at `data/cool_proof.json`.

### [DECIDED] Agentic Vision Architecture (C4, M3)
- **Decision**: Dual-tier decision engine.
  - **Tier 1**: Deterministic policy (< 1ms execution budget) handling clear threats ($c \ge 0.75$) and clear non-threats ($c < 0.40$).
  - **Tier 2**: Agentic loop for ambiguous conditions ($0.40 \le c < 0.75$). Uses `MockAgent` for fully deterministic, reproducible local testing / CI and `BedrockAgentClient` for production AWS deployments.
  - **Tool Loop**: Calls vision tools (`request_more_frames`, `escalate_human`, `intercept`), iteratively accumulating evidence to alter final decisions.

### [DECIDED] Safety Guardrails (G1 - G5)
- **Decision**: Pure functions (`zoneshield.guardrails`) evaluated after both Tier 1 and Tier 2.
- **Evaluation Order**:
  1. G1: Time-to-Intercept ($TTI \ge \text{delay} + \text{margin}$)
  2. G2: Lateral jet cone geometry alignment
  3. G3: Ambiguity threshold check
  4. G4: Pressure cooldown protection
  5. G5: Instantaneous kill switch
- Any veto overrides the agent and sets `decision.action = monitor` with an immutable audit entry.

### [DECIDED] Storage & Persistence (M4)
- **Decision**: Thread-safe SQLite repository in Write-Ahead-Logging (`PRAGMA journal_mode=WAL`) mode for local and edge deployments, structured to easily adapt to DynamoDB for AWS deployments.

### [DECIDED] Reproducible 3-Way Benchmark & Evaluation (M6)
- **Decision**:
  - `python -m benchmarks.run`: Executes micro-benchmarks (adaptiveThreshold, morphology, resize) and end-to-end pipeline benchmarks, saving `results.json`, CSV, and `BENCHMARK_REPORT.md`.
  - `python -m eval.run`: Evaluates scenarios S1-S6 against simulator ground truth, calculating precision, recall, false-interception rate, trajectory MAE, and agentic ablation.

---

## 2. Cloud Deployment Notes (AWS Graviton)
- **Local Dev / Testing**: LocalStack or Mock mode (`ZONESHIELD_AGENT_MODE=mock`).
- **AWS Production**:
  - EC2 Instance: `c7g.xlarge` (AWS Graviton3, Arm Neoverse-V1) with COOL AMI.
  - Automated cost guard via CloudWatch alarm: auto-stops instance if CPU idle $< 5\%$ for 30 minutes.
  - S3 evidence bucket lifecycle rules auto-expire temporary frames after 14 days.