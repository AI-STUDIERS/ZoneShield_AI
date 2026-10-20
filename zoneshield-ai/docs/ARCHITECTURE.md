# ZoneShield AI Architecture & Technical Design

**Tagline:** *See the Threat. Predict the Path. Protect the Zone.*

ZoneShield AI is an active vision inspection and foreign-object interception system powered by **OpenCV 5** and **AWS (Graviton + Cloud-Optimized OpenCV Library / COOL)**. Rather than passively alerting after an anomaly has already contaminated production, ZoneShield AI operates a closed, live **Perception -> Prediction -> Decision -> Action -> Verification** control loop.

---

## 1. System Architecture Overview

```mermaid
flowchart TD
    subgraph Ingestion["Ingestion Layer"]
        Sim["SimulatorLive (Digital Twin)"]
        Cam["Browser Webcam (WebRTC/WS)"]
        File["VideoFile Replay"]
    end

    subgraph Core["Vision Worker (OpenCV 5 & COOL on AWS Graviton)"]
        Ring["Frame Ring Buffer (Drop Stale / Bounded Latency)"]
        Homo["Homography & Belt Warp"]
        ROI["ROI Crop & Downscale"]
        BG["MOG2 / KNN Background Subtraction"]
        Morph["Morphology (Open/Close)"]
        Cont["findContours & Heuristic Classifier"]
        Kalman["Multi-Object Kalman Filter Tracker"]
        Pred["Trajectory Predictor (TTI & Jet Intersect)"]
    end

    subgraph Decision["Dual-Tier Decision & Safety"]
        T1["Tier 1 Policy (< 1ms Frame Budget)"]
        T2["Tier 2 LLM Agent (Amazon Bedrock / Mock)"]
        Guard["Hard Guardrails (G1 - G5)"]
        Actuator["Simulated Air-Jet Interceptor"]
        Verifier["Outcome Verifier"]
    end

    subgraph Services["Backend & Observability"]
        FastAPI["FastAPI REST & WebSocket Gateway"]
        DB["SQLite (WAL) / DynamoDB Storage"]
        Audit["Immutable Audit Log"]
        Dash["Interactive HTML5 Canvas Dashboard"]
        Human["Human Review Queue"]
    end

    Sim --> Ring
    Cam --> Ring
    File --> Ring
    Ring --> Homo --> ROI --> BG --> Morph --> Cont --> Kalman --> Pred
    Pred --> T1
    T1 -- "High Conf & Jet Aligned" --> Guard
    T1 -- "Ambiguous & Time Permits" --> T2
    T2 -- "Tool Calls (request_more_frames)" --> Kalman
    T2 -- "Escalate" --> Human
    T2 -- "Intercept Recommendation" --> Guard
    Guard -- "Approved" --> Actuator
    Guard -- "Veto (G1-G5)" --> Audit
    Actuator --> Verifier
    Verifier --> Audit
    Pred --> FastAPI
    Audit --> DB
    FastAPI --> Dash
    FastAPI --> Human
```

---

## 2. Process Model & Concurrency
- **API Gateway (`api.py`)**: Asynchronous FastAPI server handling client WebSockets, REST management, health probes, and audit streams.
- **Vision Worker (`worker.py`)**: CPU-bound pipeline running on AWS Graviton with explicit thread pinning via `cv2.setNumThreads(4)` utilizing Arm NEON SIMD vector extensions and KleidiCV primitives.
- **Frame Ring Buffer (`frame_ring_buffer.py`)**: Fixed-capacity ring buffer holding only the latest frames. When downstream processing experiences spikes, older frames are dropped rather than building queue latency, maintaining real-time fidelity.
- **Timestamps over Frame Indices**: Every calculation (velocity, trajectory, time-to-intercept) uses monotonic capture timestamps `t_capture_ms` to handle frame jitter and variable capture rates robustly.

---

## 3. Decision Engine State Machine

```mermaid
stateDiagram-v2
    [*] --> MONITORING
    MONITORING --> TRACKING: Object Detected
    TRACKING --> ASSESSING: Track Initialized (> 3 frames)
    ASSESSING --> INTERCEPTING: Confidence >= 0.75 & Timing Feasible (Tier 1)
    ASSESSING --> GATHERING_EVIDENCE: Ambiguous (0.40 <= Conf < 0.75) (Tier 2 Agent)
    GATHERING_EVIDENCE --> INTERCEPTING: Evidence Confirms Threat
    GATHERING_EVIDENCE --> AWAITING_HUMAN: Ambiguity Persists / Max Rounds Exceeded
    AWAITING_HUMAN --> INTERCEPTING: Operator Approves
    AWAITING_HUMAN --> MONITORING: Operator Dismisses / Timeout Expired
    INTERCEPTING --> VERIFYING: Actuator Impulse Fired
    VERIFYING --> MONITORING: Outcome Verified (Object Deflected)
```

---

## 4. Safety Guardrails (G1 - G5)
Guardrails sit **after both Tier 1 and Tier 2** and act as an absolute veto. No air-jet actuator firing can ever occur without passing all five checks:
1. **G1 (TTI Margin)**: Never fire if Time-To-Intercept is less than actuator mechanical delay + safety margin (`TTI < actuation_delay_ms + min_tti_margin_ms`).
2. **G2 (Jet Cone Alignment)**: Never fire if predicted lateral position `x` at `t_at_jet` is outside the physical jet dispersion cone.
3. **G3 (Ambiguity Floor)**: Never fire if threat confidence is below ambiguous floor (`confidence < t_ambiguous_low`).
4. **G4 (Cooldown Protection)**: Enforces physical cooldown period between bursts to prevent air tank pressure drop.
5. **G5 (Emergency Kill Switch)**: Hardware-level emergency stop immediately disables all actuation pathways.
