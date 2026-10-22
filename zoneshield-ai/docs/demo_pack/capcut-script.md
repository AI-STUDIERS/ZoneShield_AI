# 🎬 ZoneShield AI — CapCut Assembly Script
> **OpenCV AI Competition 2026 Submission Video**  
> Grounded directly in live recorded assets: `zoneshield_demo_1792514950259.webp` and captured stills.

---

## 📐 Project Settings (CapCut / Premiere / Resolve)

| Property | Value |
| :--- | :--- |
| **Canvas Ratio** | 16:9 Landscape (1920×1080) |
| **Frame Rate** | 30.0 fps (matches vision pipeline telemetry) |
| **Total Target Duration** | 1:00.0 (60 seconds) |
| **Export Profile** | MP4 H.264 / High Bitrate (15-20 Mbps) / AAC Audio |

---

## 🎚️ Multi-Track Layout

```
[V3] Top Overlays    : Technical Callout Badges & Competition Watermark
[V2] Middle Overlays : Animated Arrows & Zoom Highlights (from captured stills)
[V1] Base Video      : Live Digital Twin Screen Recording (zoneshield_demo.webp)
--------------------------------------------------------------------------------
[A1] Voiceover (VO)  : Clear, authoritative technical narration (-3 dB)
[A2] Sound FX (SFX)  : Pneumatic air hiss at 0:18, Safety alarm click at 0:30 (-12 dB)
[A3] Background BGM  : Sleek cybernetic/minimalist synth pulse (-22 dB ducked)
```

---

## ⏱️ Timeline & Scene Breakdown

### Scene 1: Introduction & Live Telemetry Overview (0:00.0 – 0:15.0)
- **Asset**: `zoneshield_demo_1792514950259.webp` (0:00 – 0:15)
- **Still Reference**: `dashboard_initial_1792514973879.png`
- **On-Screen Text**:
  - `ZoneShield AI` (Title, bold white/blue gradient)
  - `OpenCV 5 + AWS Graviton (KleidiCV COOL Acceleration)`
- **VO Script**:
  > *"Welcome to ZoneShield AI — an active conveyor threat interception digital twin built for the OpenCV AI Competition 2026. Powered by OpenCV 5 and AWS Graviton with KleidiCV COOL acceleration, the system achieves a deterministic 30 FPS pipeline rate with under 13 milliseconds of compute budget."*
- **Editing Action**:
  1. Place base recording onto **V1** from 0:00 to 0:15.
  2. Add spotlight zoom (scale: 115%) focused on the header badges (`COOL GRAVITON: ACTIVE` and `SAFETY: NORMAL`).
  3. Fade in title card on **V2** for 3.5 seconds.

---

### Scene 2: Dual-Tier Perception & Simulated Actuation (0:15.0 – 0:30.0)
- **Asset**: `zoneshield_demo_1792514950259.webp` (0:15 – 0:30)
- **Still Reference**: `manual_fire_state_1792514994825.png`
- **On-Screen Text**:
  - `Tier-1 Deterministic CV (<15ms)` → `Simulated Air-Jet Intercept`
  - `Hard Constraint C1: Digital Twin (Simulated Actuator Only)`
- **VO Script**:
  > *"As objects traverse the belt, Tier-1 OpenCV detection computes lateral coordinates and predicts trajectory. When a target crosses the air-jet interceptor line within the dispersion cone, the system commands an intercept. Hard Constraint C1 is strictly enforced: all actuation is simulated inside our zero-hardware digital twin."*
- **Editing Action**:
  1. At 0:18, when the manual actuator burst triggers, synchronize a pneumatic air hiss sound on **A2**.
  2. Overlay a circular highlight ripple on the canvas air-jet puff.
  3. Show the `[ACTUATOR] Air-Jet SIMULATED impulse fired` log in the decision feed.

---

### Scene 3: Emergency Safety Guardrail G5 (0:30.0 – 0:45.0)
- **Asset**: `zoneshield_demo_1792514950259.webp` (0:30 – 0:45)
- **Still Reference**: `kill_switch_active_1792515007918.png`
- **On-Screen Text**:
  - `Safety Guardrail G5: Instantaneous Emergency Kill Switch`
  - `Status: SAFETY: KILLED (Actuation Halted)`
- **VO Script**:
  > *"Safety is paramount. Under Guardrail G5, tripping the emergency kill switch instantly halts all actuation commands and locks the safety state to KILLED. Once cleared, normal operation resumes with an immutable, cryptographically verifiable audit trace."*
- **Editing Action**:
  1. Add a subtle red vignette border pulse on **V3** when the kill switch turns red at 0:32.
  2. Zoom into the `SAFETY: KILLED` indicator badge.
  3. Show the recovery back to `SAFETY: NORMAL` when reset is clicked.

---

### Scene 4: Agentic Reasoning & Competition Wrap-up (0:45.0 – 1:00.0)
- **Asset**: `zoneshield_demo_1792514950259.webp` (0:45 – 1:00)
- **Still Reference**: `final_stable_state_1792515059375.png`
- **On-Screen Text**:
  - `Bounded Ring Buffer (Zero Memory Leak)`
  - `Ready for OpenCV AI Competition 2026`
- **VO Script**:
  > *"With bounded ring buffering, multi-object Kalman tracking, and Bedrock-backed agentic escalation for ambiguous threats, ZoneShield AI delivers verifiable edge AI for industrial safety. Thank you."*
- **Editing Action**:
  1. Show full dashboard layout.
  2. Fade to black over 1.5 seconds.
  3. Display GitHub repository link and OpenCV competition acknowledgment.

---

## 🗂️ Asset Directory Reference

| Type | Path |
| :--- | :--- |
| **Video Recording** | `docs/demo_pack/zoneshield_demo.webp` (or artifact video) |
| **Still 1 (Dashboard)** | `docs/images/dashboard_telemetry_hud.png` |
| **Still 2 (Manual Burst)** | `docs/images/manual_actuator_burst.png` |
| **Still 3 (Kill Switch)** | `docs/images/kill_switch_guardrail_active.png` |
| **Still 4 (Final State)** | `docs/images/stream_tracking_trajectories.png` |
