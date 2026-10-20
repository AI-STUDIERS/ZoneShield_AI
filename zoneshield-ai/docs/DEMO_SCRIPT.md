# ZoneShield AI — 3-Minute Video Demo Script

**Competition:** OpenCV AI Competition 2026, powered by AWS  
**Target Award Categories:** Overall Award, Best Use of COOL Award, Agentic Vision Award  
**Duration:** Exactly 3 Minutes (180 Seconds)

---

### Segment 1: The Problem (0:00 - 0:15 | 15s)
- **Visual:** Camera on narrator / slide showing fast industrial conveyor belt carrying food items or parts. An alert pops up on screen *after* a bolt has entered the packaging box.
- **Narrator:**
  > "Conventional computer vision stops at detection. On modern high-speed conveyors running at hundreds of millimeters per second, by the time an anomaly alert pops up on an operator screen, the contaminant has already entered the protected zone. In food processing and precision manufacturing, a late alert is as useless as no alert at all."

---

### Segment 2: Introducing ZoneShield AI & Live Loop (0:15 - 1:15 | 60s)
- **Visual:** Screen switches to the ZoneShield AI live HTML5 Canvas dashboard. Objects flow down the simulated belt. Green circles are legitimate items; red objects are threats. Trajectory lines project forward into the yellow Shield Zone. An air-jet impulse animation deflects the contaminant safely.
- **Narrator:**
  > "This is ZoneShield AI. We built a closed Perception -> Prediction -> Decision -> Action -> Verification loop running live on OpenCV 5 and AWS Graviton.
  >
  > Notice the protected polygon: the Shield Zone. As items enter the field of view, our OpenCV pipeline performs background subtraction, morphology, and contour classification.
  >
  > Next, a Kalman filter tracks each item and computes physical velocity in millimeters per second using capture timestamps. We project the future trajectory to calculate the exact Time-to-Intercept. When a threat crosses our simulated air-jet line, our digital twin fires a calibrated lateral impulse, diverting the threat before it ever touches the protected zone."

---

### Segment 3: Agentic Vision in Action (1:15 - 1:55 | 40s)
- **Visual:** Split screen showing the decision inspector and review queue. Scenario S2 plays: an object partially occluded triggers `gather_evidence`, requests 5 more frames, re-estimates confidence, and proceeds to intercept. Then Scenario S3 plays: look-alike harmless item is withheld from interception.
- **Narrator:**
  > "What makes ZoneShield AI agentic? Visual evidence demonstrably guides downstream actions.
  >
  > In clear-cut cases, our Tier 1 policy decides in under one millisecond. But when confidence falls into the ambiguous band—like partial occlusion or glare—our Tier 2 Agent steps in.
  >
  > Watch Scenario S2: initial confidence was only 50%. The agent called `request_more_frames`. As fresh visual crops accumulated, confidence rose to 85%, authorizing a clean interception. In Scenario S3, the agent recognized a harmless look-alike, withholding the actuator and preventing costly production downtime."

---

### Segment 4: AWS Graviton & COOL Acceleration (1:55 - 2:35 | 40s)
- **Visual:** Terminal running `python -m zoneshield.selfcheck` and benchmark comparisons showing B1 (x86), B2 (Graviton Stock), and B3 (Graviton + COOL). Graphs from `results/` displaying throughput and latency.
- **Narrator:**
  > "ZoneShield AI is engineered from the ground up for AWS Graviton with the Cloud-Optimized OpenCV Library (COOL).
  >
  > Our self-check tool verifies OpenCV 5 and runtime Arm NEON SIMD acceleration. In our 3-way benchmark across identical seeded workloads, COOL on Graviton3 achieves over 120 FPS—delivering a 19% cost reduction per million inspected items compared to x86 instances, while providing rock-solid sub-frame latency."

---

### Segment 5: Safety, Guardrails & Conclusion (2:35 - 3:00 | 25s)
- **Visual:** Operator clicks "Manual Fire" and toggles the red "Kill Switch". Dashboard status immediately updates to "SAFETY: KILLED".
- **Narrator:**
  > "Every single action is governed by five pure-function safety guardrails—verifying Time-to-Intercept margins, jet cone geometry, and an instantaneous hardware kill switch.
  >
  > ZoneShield AI: See the Threat. Predict the Path. Protect the Zone. Fully open, reproducible, and cloud-ready."
