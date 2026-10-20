# ZoneShield AI — Limitations and Failure Modes

In compliance with Truth Rule **T4** (*Document limitations and failure cases openly*), this document details current known constraints, boundary conditions, and performance envelopes.

---

## 1. Physical & Optical Boundary Conditions
- **High-Velocity Conveyor Drift**: At conveyor belt velocities exceeding $2.5\times$ baseline ($> 300\text{ mm/s}$), the available Time-to-Intercept (TTI) drops below the actuator delay ($80\text{ ms}$) + safety margin ($150\text{ ms}$). In this regime, Guardrail **G1** appropriately blocks firing and logs a missed interception to prevent mistimed actuator damage.
- **Extreme Specular Glare & Illumination Shifts**: Harsh specular glare on shiny metallic conveyor surfaces can overwhelm classical background subtraction. In such scenarios (Scripted Scenario S4), confidence drops into the ambiguous regime and triggers operator review rather than false interception.
- **Physical Collision Cascades**: The digital twin assumes isolated particles and independent lateral trajectory drift. Inter-particle collisions or rolling tumbling dynamics require an advanced rigid-body physics engine (e.g., PyBullet / MuJoCo) for millimeter accuracy.

---

## 2. Cloud Latency & Network Budget
- **Tier 2 LLM Agent Call Overhead**: When routing ambiguous visual evidence to Amazon Bedrock, round-trip inference latency typically ranges between $800\text{ ms}$ and $1800\text{ ms}$. If an incoming object has a TTI smaller than this time budget, the decision engine automatically skips Tier 2 and defaults to a safe Tier 1 fallback (monitoring while logging the incident).
- **Network Jitter on Remote Ingest**: When operating over WebSocket ingests from external IP cameras or browser webcams, network jitter can cause frame bursts. The Frame Ring Buffer drops stale frames to preserve real-time responsiveness, but severe packet loss degrades Kalman velocity convergence.

---

## 3. COOL Performance Observations
- **Accelerated Primitives**: Cloud-Optimized OpenCV Library (COOL) on AWS Graviton demonstrates significant throughput uplift on **adaptive Gaussian thresholding**, **morphological filtering**, and **bilinear/bicubic image resizing** due to Arm NEON vectorization and KleidiCV optimizations.
- **Non-Accelerated Stages**: Operations dominated by memory-bus transfer or sequential contour topology traversing (such as `findContours` on high-density noise) exhibit lower relative acceleration than purely vectorized pixel kernels.
